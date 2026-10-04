"""Independent scientific contexts and Wigger geographic review."""
from datetime import date
from uuid import uuid4
from sqlalchemy import select,func
import pytest
from fastapi import HTTPException
from app.api.dependencies import get_hydrology_engine
from app.main import app
from app.db.session import get_db
from app.db.models import CaseModel,TargetSpeciesModel,ReplicateObservationModel
from app.api.routes.demo import load_wigger_demo
from app.api.routes.sampling import get_sampling_service,evaluate_sampling_decision,persist_sampling_candidates
from app.api.routes.detection_contexts import register_species,register_detection_context,record_observation,register_detection_site,validate_source_network
from app.schemas.detection_contexts import SpeciesCreate,DetectionContextCreate,DetectionSiteCreate,ObservationCreate
from app.domain.enums import ValidationStatus
from app.repositories.detection_contexts import detection_scope
from app.repositories.sampling import SamplingRepository
from app.repositories.cases import CaseRepository
from app.repositories.evidence import EvidenceRepository
from app.services.location_matching import LocationMatchingService
from app.services.one_health_service import OneHealthService
from tests.unit.test_case_creation_integration import _post_json
from tests.unit.test_investigation_runs import _service


def extra(db,case_id,taxon='Salmo trutta',site_id=None,day=26):
    species=register_species(case_id,SpeciesCreate(taxon=taxon),db)
    return register_detection_context(case_id,DetectionContextCreate(species_id=species['id'],
        site_id=site_id or db.get(CaseModel,case_id).detection_site_id,sampled_on=date(2014,6,day)),db)


def observe(db,case_id,context,results):
    return record_observation(case_id,context['id'],ObservationCreate(source='Synthetic observations',replicate_results=results,provenance={'synthetic':True}),db)


def test_species_events_replicates_and_onehealth_are_isolated(db_session):
    demo=load_wigger_demo(db_session)
    contexts=[extra(db_session,demo.case_id),extra(db_session,demo.case_id,day=27),extra(db_session,demo.case_id,taxon='Third species')]
    for context,results in zip(contexts,[['Positive','Negative'],['Negative'],['Invalid','Positive']]):
        item=observe(db_session,demo.case_id,context,results)
        with detection_scope(db_session,context['id']):
            evidence=EvidenceRepository(db_session).get_evidence_by_case(demo.case_id)
            assert len(evidence)==1 and evidence[0].id==item['evidence_id']
            assert evidence[0].value['replicate_results']==results
            case=CaseRepository(db_session).get_case_by_id(demo.case_id)
            assert case.target_taxon==context['target_taxon'] and case.observation_date==context['sampled_on']
            assert not OneHealthService(db_session).assess(demo.case_id)['pathways']
    assert db_session.scalar(select(func.count()).select_from(TargetSpeciesModel))==3
    assert db_session.scalar(select(func.count()).select_from(ReplicateObservationModel))==5
    assert len(EvidenceRepository(db_session).get_evidence_by_case(demo.case_id))==4
    assert OneHealthService(db_session).assess(demo.case_id)['pathways']


def test_context_hypotheses_decisions_candidates_and_history(db_session):
    demo=load_wigger_demo(db_session);service=get_sampling_service(db_session)
    original=evaluate_sampling_decision(demo.case_id,db_session,service)
    context=extra(db_session,demo.case_id);observe(db_session,demo.case_id,context,['Negative'])
    repo=SamplingRepository(db_session);zones=repo.get_zones_by_case(demo.case_id)
    with detection_scope(db_session,context['id']):
        assert repo.get_zones_by_case(demo.case_id)==[]
        assert not any(site.label in ('Site B','Site C','Site D') for site in repo.get_sites_by_case(demo.case_id))
        assert repo.get_latest_decision_for_case(demo.case_id) is None
        assert _service(db_session).list(demo.case_id)==[]
        for zone in zones[:2]:
            repo.create_zone(case_id=demo.case_id,label=zone.label,root_hyriv_id=zone.root_hyriv_id,
                reach_ids=zone.reach_ids,validation_status=ValidationStatus.NOT_VERIFIED)
        for zone in repo.get_zones_by_case(demo.case_id):validate_source_network(demo.case_id,zone.id,True,db_session)
        run=_service(db_session).reinvestigate(demo.case_id)
        assert len(run['hypotheses'])==2 and run['previous_decision_id'] is None
        assert all(item['unknown']==1 and item['status']=='UNKNOWN' for item in run['hypotheses'])
        ids={item.site_id for item in persist_sampling_candidates(demo.case_id,db_session,service).candidates}
        assert len(_service(db_session).list(demo.case_id))==1
    assert repo.get_latest_decision_for_case(demo.case_id).id==original.id
    assert not _service(db_session).list(demo.case_id)
    assert not ids.intersection({item.site_id for item in persist_sampling_candidates(demo.case_id,db_session,service).candidates})


def test_separate_detection_site_and_fraction(db_session):
    demo=load_wigger_demo(db_session)
    site=register_detection_site(demo.case_id,DetectionSiteCreate(label='Reviewed upstream site',latitude=47.1729166666,longitude=7.99375,hyriv_id=20450127,confirmed=True),db_session)
    context=extra(db_session,demo.case_id,site_id=site.id)
    observe(db_session,demo.case_id,context,['Positive'])
    with detection_scope(db_session,context['id']):
        case=CaseRepository(db_session).get_case_by_id(demo.case_id)
        assert case.detection_site_id==site.id and case.target_taxon=='Salmo trutta'
        from app.services.sampling_service import detection_fraction
        stored=SamplingRepository(db_session).get_site_by_id(site.id)
        assert 0<=detection_fraction(stored,0.8574)<=1 and stored.validation_status.value=='MATCHED'


@pytest.mark.parametrize('resource',['context','site','species','evidence','decision','candidate'])
def test_cross_case_context_references(db_session,resource):
    demo=load_wigger_demo(db_session);context=extra(db_session,demo.case_id)
    decision=evaluate_sampling_decision(demo.case_id,db_session,get_sampling_service(db_session))
    app.dependency_overrides[get_db]=lambda:db_session
    app.dependency_overrides[get_hydrology_engine]=lambda:get_sampling_service(db_session).hydrology_engine
    try:
        base=f'/cases/{demo.case_id}';query=f'?detection_context_id={context["id"]}'
        if resource=='context':status,_=_post_json(base+f'?detection_context_id={uuid4()}',{},method='GET')
        elif resource in ('site','species'):
            payload={'species_id':str(context['species_id']),'site_id':str(context['site_id']),'sampled_on':'2014-06-28'};payload[resource+'_id']=str(uuid4())
            status,_=_post_json(base+'/detection-contexts',payload)
        elif resource=='evidence':
            evidence=EvidenceRepository(db_session).get_evidence_by_case(demo.case_id)[0]
            observe(db_session,demo.case_id,context,['Positive'])
            status,_=_post_json(base+'/reinvestigate'+query,{'trigger_evidence_id':str(evidence.id)})
        elif resource=='decision':status,_=_post_json(base+'/decision-trace'+query+f'&decision_id={decision.id}',{},method='GET')
        else:
            candidate=persist_sampling_candidates(demo.case_id,db_session,get_sampling_service(db_session)).candidates[0]
            payload={'candidate_reference':str(candidate.site_id),'hyriv_id':candidate.hyriv_id,'sampled_at':'2024-01-01T00:00:00','replicate_count':1,'positive_replicates':1,'assay':'Synthetic','controls_status':'PASS','collector_source':'test','provenance':{'synthetic':True}}
            status,_=_post_json(base+'/follow-up-samples'+query,payload)
        assert status==404
    finally:app.dependency_overrides.clear()


def test_bulk_creation_atomic_observations(db_session):
    primary={'target_taxon':'Synthetic primary','observation_date':'2014-06-25','detection_site_latitude':47.3140004,'detection_site_longitude':7.8954007,'detection_site_hyriv_id':20446064,
        'initial_evidence':[{'evidence_type':'edna_observation','source':'Synthetic source','value':{'replicate_results':['Positive']},'provenance':{'synthetic':True}}]}
    additional={'taxon':'Synthetic secondary','sampled_on':'2014-06-26','observation':{'replicate_results':['Negative'],'source':'Synthetic source','provenance':{'synthetic':True}}}
    app.dependency_overrides[get_db]=lambda:db_session
    app.dependency_overrides[get_hydrology_engine]=lambda:get_sampling_service(db_session).hydrology_engine
    try:
        status,body=_post_json('/cases/multi-detection',{'primary':primary,'additional_contexts':[additional]})
        assert status==201 and len(body['detection_contexts'])==1
        assert db_session.scalar(select(func.count()).select_from(CaseModel))==1
        assert db_session.scalar(select(func.count()).select_from(ReplicateObservationModel))==2
        status,_=_post_json('/cases/multi-detection',{'primary':primary,'additional_contexts':[{**additional,'reuse_site_index':10}]})
        assert status==422 and db_session.scalar(select(func.count()).select_from(CaseModel))==1
    finally:app.dependency_overrides.clear()


def test_geometry_matching_and_frozen_site_a(monkeypatch):
    service=LocationMatchingService();result=service.match(47.3140004,7.8954007)
    assert result['status']=='CLOSE' and result['review_required']
    assert result['alternatives'][0]['hyriv_id']==20446064
    assert result['alternatives'][0]['snap_distance_m']==pytest.approx(64.81356,abs=0.03)
    confirmed=service.confirm(47.3140004,7.8954007,20446064,True)
    assert confirmed['metadata']['network_source'].endswith('site_a.json')
    assert confirmed['snap_distance_m']==pytest.approx(64.81356293400535)
    with pytest.raises(HTTPException):service.confirm(47.3140004,7.8954007,20446064,False)
    assert service.match(0,0)['status']=='UNSUPPORTED'
    with pytest.raises(HTTPException):service.confirm(0,0,20446064,True)
    monkeypatch.setenv('WIGGER_MATCH_CLOSE_M','1');assert service.match(47.3140004,7.8954007)['status']=='DISTANT'
    monkeypatch.setenv('WIGGER_MATCH_MAX_M','10000');monkeypatch.setenv('WIGGER_MATCH_AMBIGUITY_M','10000');assert service.match(47.3140004,7.8954007)['status']=='AMBIGUOUS'


def test_natural_ambiguous_junction_requires_selected_alternative():
    service=LocationMatchingService()
    result=service.match(47.310416676985575,7.90208334110692)
    assert result['status']=='AMBIGUOUS'
    assert len(result['alternatives'])>=2 and result['review_required']
    chosen=result['alternatives'][0]['hyriv_id']
    with pytest.raises(HTTPException):service.confirm(result['latitude'],result['longitude'],chosen,False)
    reviewed=service.confirm(result['latitude'],result['longitude'],chosen,True)
    assert reviewed['validation_status']=='MATCHED'


def test_reviewed_fractions_drive_registered_distance(db_session):
    demo=load_wigger_demo(db_session)
    site=register_detection_site(demo.case_id,DetectionSiteCreate(label='Reviewed upstream',latitude=47.1729166666,longitude=7.99375,hyriv_id=20450127,confirmed=True),db_session)
    repo=SamplingRepository(db_session);service=get_sampling_service(db_session)
    detection=repo.get_site_by_id(demo.detection_site_id)
    source=repo.get_site_by_id(site.id)
    info=service.registered_candidate_distances([source],detection)[source.id]
    assert info['network_distance_km'] is not None
    # Coordinate match is within the frozen B tolerance: frozen reference stays authoritative.
    assert info['network_distance_status']=='VALIDATED_REFERENCE'
    reverse=service.registered_candidate_distances([detection],source)[detection.id]
    assert reverse['network_distance_km'] is None and 'No directed' in reverse['network_distance_reason']
    from app.services.location_matching import validated_geometry
    from pyproj import Transformer
    geometry=validated_geometry()[0][20450127]
    point=geometry.interpolate(0.4,normalized=True)
    longitude,latitude=Transformer.from_crs('EPSG:2056','EPSG:4326',always_xy=True).transform(point.x,point.y)
    matched=register_detection_site(demo.case_id,DetectionSiteCreate(label='Geometry-derived position',
        latitude=latitude,longitude=longitude,hyriv_id=20450127,confirmed=True),db_session)
    position=repo.get_site_by_id(matched.id)
    derived=service.registered_candidate_distances([position],detection)[position.id]
    assert derived['network_distance_status']=='GEOMETRY_DERIVED'
    fraction=position.metadata['selected_match']['fraction_along_reach']
    assert derived['network_distance_km']==pytest.approx(service.hydrology_engine.network_distance_km(
        20450127,detection.hyriv_id,fraction,service.site_a_fraction))
