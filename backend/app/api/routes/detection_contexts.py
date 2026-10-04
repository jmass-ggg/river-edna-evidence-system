from app.api.dependencies import get_hydrology_engine
"""Species, reusable detection sites and independent sampling contexts."""
from uuid import UUID
from datetime import datetime,time
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db.session import get_db
from app.db.models import CaseModel,TargetSpeciesModel,DetectionContextModel,SamplingSiteModel,ReplicateObservationModel
from app.api.detection_scope import bind_detection_context
from app.repositories.detection_contexts import ensure_primary,detection_scope
from app.repositories.sampling import SamplingRepository
from app.repositories.evidence import EvidenceRepository
from app.schemas.detection_contexts import MultiDetectionInvestigationCreate,SpeciesCreate,DetectionSiteCreate,DetectionContextCreate,ObservationCreate
from app.domain.enums import SiteType,ValidationStatus
from app.services.location_matching import LocationMatchingService

router=APIRouter(prefix='/cases',tags=['detection contexts'],dependencies=[Depends(bind_detection_context)])

def parent(db,case_id):
    case=db.get(CaseModel,case_id)
    if case is None:raise HTTPException(404,detail={'type':'NotFoundError','message':'Investigation not found'})
    return case

def serialize(db,row):
    species=db.get(TargetSpeciesModel,row.species_id);site=db.get(SamplingSiteModel,row.site_id)
    return {'id':row.id,'case_id':row.case_id,'species_id':row.species_id,'target_taxon':species.taxon,
        'site_id':row.site_id,'site_label':site.label,'sampled_on':row.sampled_on,'event_label':row.event_label,
        'is_primary':row.is_primary,'created_at':row.created_at}

@router.get('/{case_id}/species')
def list_species(case_id:UUID,db=Depends(get_db)):
    parent(db,case_id)
    return [{'id':row.id,'taxon':row.taxon} for row in db.scalars(select(TargetSpeciesModel).where(TargetSpeciesModel.case_id==case_id).order_by(TargetSpeciesModel.taxon))]

@router.post('/{case_id}/species',status_code=201)
def register_species(case_id:UUID,request:SpeciesCreate,db=Depends(get_db)):
    parent(db,case_id)
    row=db.scalar(select(TargetSpeciesModel).where(TargetSpeciesModel.case_id==case_id,TargetSpeciesModel.taxon==request.taxon))
    if row is None:
        row=TargetSpeciesModel(case_id=case_id,taxon=request.taxon);db.add(row);db.commit();db.refresh(row)
    return {'id':row.id,'taxon':row.taxon}

@router.post('/{case_id}/detection-sites',status_code=201)
def register_detection_site(case_id:UUID,request:DetectionSiteCreate,db=Depends(get_db)):
    parent(db,case_id)
    validation=LocationMatchingService().confirm(request.latitude,request.longitude,request.hyriv_id,request.confirmed)
    repo=SamplingRepository(db)
    site=repo.create_site(case_id=case_id,label=request.label,latitude=request.latitude,longitude=request.longitude,
        hyriv_id=request.hyriv_id,site_type=SiteType.DETECTION_SITE,
        validation_status=ValidationStatus(validation['validation_status']),network_latitude=validation.get('network_latitude'),
        network_longitude=validation.get('network_longitude'),snap_distance_m=validation.get('snap_distance_m'),metadata=validation['metadata'])
    from app.schemas.sampling import SamplingSiteResponse
    return SamplingSiteResponse.model_validate(site)

@router.get('/{case_id}/detection-contexts')
def list_detection_contexts(case_id:UUID,species_id:UUID|None=None,db=Depends(get_db)):
    parent(db,case_id)
    query=select(DetectionContextModel).where(DetectionContextModel.case_id==case_id)
    if species_id:query=query.where(DetectionContextModel.species_id==species_id)
    return [serialize(db,row) for row in db.scalars(query.order_by(DetectionContextModel.created_at,DetectionContextModel.id))]

@router.post('/{case_id}/detection-contexts',status_code=201)
def register_detection_context(case_id:UUID,request:DetectionContextCreate,db=Depends(get_db)):
    parent(db,case_id)
    species=db.get(TargetSpeciesModel,request.species_id);site=db.get(SamplingSiteModel,request.site_id)
    if species is None or species.case_id!=case_id or site is None or site.case_id!=case_id or site.site_type!=SiteType.DETECTION_SITE.value:
        raise HTTPException(404,detail={'type':'NotFoundError','message':'Species and physical detection site must belong to this investigation'})
    row=DetectionContextModel(case_id=case_id,**request.model_dump());db.add(row)
    try:db.commit();db.refresh(row)
    except Exception:db.rollback();raise
    return serialize(db,row)

@router.post('/{case_id}/detection-contexts/{context_id}/observations',status_code=201)
def record_observation(case_id:UUID,context_id:UUID,request:ObservationCreate,db=Depends(get_db)):
    row=db.get(DetectionContextModel,context_id)
    if row is None or row.case_id!=case_id:raise HTTPException(404,detail={'type':'NotFoundError','message':'Detection context not found in investigation'})
    try:
        with detection_scope(db,context_id):
            evidence=EvidenceRepository(db).add_evidence(case_id=case_id,evidence_type='edna_observation',source=request.source,
                value={'replicate_results':request.replicate_results,'assay_metadata':request.assay_metadata},
                observed_at=datetime.combine(row.sampled_on,time.min),provenance=request.provenance,commit=False)
            db.commit()
            return {'evidence_id':evidence.id,'detection_context_id':context_id,'replicate_results':request.replicate_results}
    except Exception:db.rollback();raise

@router.get('/{case_id}/observations')
def list_observations(case_id:UUID,species_id:UUID|None=None,detection_context_id:UUID|None=None,db=Depends(get_db)):
    parent(db,case_id)
    query=select(ReplicateObservationModel).join(DetectionContextModel,ReplicateObservationModel.detection_context_id==DetectionContextModel.id).where(ReplicateObservationModel.case_id==case_id)
    if species_id:query=query.where(DetectionContextModel.species_id==species_id)
    if detection_context_id:query=query.where(ReplicateObservationModel.detection_context_id==detection_context_id)
    return [{'id':row.id,'detection_context_id':row.detection_context_id,'evidence_id':row.evidence_id,
             'replicate_index':row.replicate_index,'result':row.result} for row in db.scalars(query.order_by(ReplicateObservationModel.evidence_id,ReplicateObservationModel.replicate_index))]

@router.post('/{case_id}/zones/{zone_id}/validate-network')
def validate_source_network(case_id:UUID,zone_id:UUID,confirmed:bool=False,db=Depends(get_db)):
    """Explicit graph review: validate routing, not the biological hypothesis."""
    from app.db.models import CandidateZoneModel
    from app.repositories.detection_contexts import belongs
    from app.api.routes.sampling import get_sampling_service
    from app.repositories.cases import CaseRepository
    zone=db.get(CandidateZoneModel,zone_id)
    if not belongs(db,zone,case_id):raise HTTPException(404,detail={'type':'NotFoundError','message':'Source zone not found in this detection context'})
    if not confirmed:raise HTTPException(422,detail={'type':'ValidationError','message':'Explicit network review confirmation is required'})
    service=get_sampling_service(db);engine=service.hydrology_engine
    case=CaseRepository(db).get_case_by_id(case_id);detection=SamplingRepository(db).get_site_by_id(case.detection_site_id)
    if detection.validation_status not in (ValidationStatus.MATCHED,ValidationStatus.VERIFIED):
        raise HTTPException(422,detail={'type':'IncompleteScientificPrerequisites','message':'Detection requires a reviewed geographic network match'})
    try:
        members=set(zone.reach_ids)
        if zone.root_hyriv_id not in members:raise ValueError('Root must be included in zone')
        for reach in members:
            engine.get_reach(reach)
            if reach != zone.root_hyriv_id and not set(engine.get_downstream_path(reach,zone.root_hyriv_id)).issubset(members):raise ValueError('Zone omits connecting reaches')
        path=[detection.hyriv_id] if zone.root_hyriv_id==detection.hyriv_id else engine.get_downstream_path(zone.root_hyriv_id,detection.hyriv_id)
    except ValueError as exc:raise HTTPException(422,detail={'type':'InvalidSourceZone','message':str(exc)}) from exc
    from app.scientific.data_loader import WiggerPreflightLoader
    hashes=WiggerPreflightLoader().validate_frozen_reference()
    zone.validation_status='MATCHED'
    zone.meta={**zone.meta,'network_review':{'method':'validated directed NEXT_DOWN traversal','path':path,
        'artifact_sha256':hashes,'biological_source_verified':False}}
    db.commit()
    return {'zone_label':zone.label,'network_validation_status':'MATCHED',
            'biological_source_status':'UNKNOWN','reason':'Directed network relationship reviewed; no biological source verification is inferred.'}


@router.post('/multi-detection',status_code=201)
def create_multi_detection(request: MultiDetectionInvestigationCreate,db=Depends(get_db),hydrology_engine=Depends(get_hydrology_engine)):
    """Atomic creation; every species/event owns separate observation records."""
    from app.api.routes.cases import create_case_records,get_case_service
    from app.api.dependencies import get_hydrology_engine
    from app.schemas.sampling import SamplingSiteResponse
    try:
        case=create_case_records(request.primary,db,get_case_service(db),hydrology_engine,commit=False)
        physical_sites=[case.detection_site_id]
        created=[]
        for item in request.additional_contexts:
            species=db.scalar(select(TargetSpeciesModel).where(TargetSpeciesModel.case_id==case.id,TargetSpeciesModel.taxon==item.taxon))
            if species is None:
                species=TargetSpeciesModel(case_id=case.id,taxon=item.taxon);db.add(species);db.flush()
            if item.detection_site:
                site_request=item.detection_site
                validation=LocationMatchingService().confirm(site_request.latitude,site_request.longitude,site_request.hyriv_id,site_request.confirmed)
                site=SamplingRepository(db).create_site(case_id=case.id,label=site_request.label,
                    latitude=site_request.latitude,longitude=site_request.longitude,hyriv_id=site_request.hyriv_id,
                    site_type=SiteType.DETECTION_SITE,validation_status=ValidationStatus(validation['validation_status']),
                    network_latitude=validation.get('network_latitude'),network_longitude=validation.get('network_longitude'),
                    snap_distance_m=validation.get('snap_distance_m'),metadata=validation['metadata'],commit=False)
                physical_sites.append(site.id);site_id=site.id
            else:
                if item.reuse_site_index>=len(physical_sites):raise HTTPException(422,detail={'type':'ValidationError','message':'Referenced physical site has not been registered'})
                site_id=physical_sites[item.reuse_site_index]
            context=DetectionContextModel(case_id=case.id,species_id=species.id,site_id=site_id,sampled_on=item.sampled_on,event_label=item.event_label)
            db.add(context);db.flush()
            if item.observation:
                with detection_scope(db,context.id):
                    EvidenceRepository(db).add_evidence(case_id=case.id,evidence_type='edna_observation',
                        source=item.observation.source,value={'replicate_results':item.observation.replicate_results,'assay_metadata':item.observation.assay_metadata},
                        observed_at=datetime.combine(item.sampled_on,time.min),provenance=item.observation.provenance,commit=False)
            created.append(serialize(db,context))
        db.commit()
        return {'case':case,'detection_contexts':created}
    except Exception:db.rollback();raise
