"""Explicitly opted-in PostgreSQL migration, transaction and concurrency tests.

FRESHWATER_TEST_POSTGRES_URL must identify a disposable database whose name
starts with freshwater_test_. Never run against the application database.
"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
from pathlib import Path
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.api.routes.demo import load_wigger_demo
from app.api.routes.sampling import evaluate_sampling_decision, get_sampling_service
from app.db.models import CaseModel, CandidateZoneModel, EvidenceItemModel, SamplingSiteModel
from app.repositories.evidence import EvidenceRepository
from app.repositories.sampling import SamplingRepository
from app.services.one_health_service import OneHealthService
from tests.unit.test_investigation_runs import _service


@pytest.fixture(scope="module")
def pg_engine():
    configured = os.environ.get("FRESHWATER_TEST_POSTGRES_URL")
    if not configured:
        pytest.skip("Disposable PostgreSQL URL not supplied")
    url = make_url(configured)
    if url.get_backend_name() != "postgresql" or not url.database.startswith("freshwater_test_"):
        pytest.fail("Refusing PostgreSQL integration tests outside a freshwater_test_ database")
    from config import config
    if make_url(config.DATABASE_URL) != url:
        pytest.fail("DATABASE_URL must also identify the disposable test database for Alembic")
    root = Path(__file__).resolve().parents[2]
    migration = Config(str(root / "alembic.ini"))
    migration.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(migration, "head")
    engine = create_engine(url, pool_size=6, max_overflow=2)
    yield engine, migration
    engine.dispose()


@pytest.fixture
def postgres(pg_engine):
    engine, migration = pg_engine
    # The explicit database-name guard above applies to this cleanup as well.
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE cases, sampling_sites, candidate_zones, evidence_items, sampling_decisions, decision_traces, follow_up_samples, investigation_runs, hypothesis_states, generated_candidate_snapshots CASCADE"))
    return engine, migration


def test_concurrent_demo_requests_create_one_complete_reference(postgres):
    engine, _ = postgres
    def request(_):
        with Session(engine) as db:
            return load_wigger_demo(db).case_id
    with ThreadPoolExecutor(max_workers=6) as pool:
        identities = list(pool.map(request, range(6)))
    assert len(set(identities)) == 1
    with Session(engine) as db:
        assert [db.scalar(select(func.count()).select_from(model)) for model in
                (CaseModel, SamplingSiteModel, CandidateZoneModel, EvidenceItemModel)] == [1, 4, 3, 4]
        case = db.get(CaseModel, identities[0])
        assert db.get(SamplingSiteModel, case.detection_site_id).case_id == case.id
        observation = db.scalar(select(EvidenceItemModel).where(EvidenceItemModel.evidence_type == "historical_edna_measurement"))
        assert observation.observed_at == datetime(2014, 6, 25)
        assert OneHealthService(db).assess(case.id)["observation_provenance"] == "VERIFIED_REFERENCE"


@pytest.mark.parametrize("method", ["create_site", "create_zone", "add_evidence"])
def test_postgresql_partial_writes_roll_back_and_retry(postgres, monkeypatch, method):
    engine, _ = postgres
    cls = EvidenceRepository if method == "add_evidence" else SamplingRepository
    original = getattr(cls, method)
    calls = 0
    def fail_after_first_write(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("PostgreSQL injected failure")
        return original(*args, **kwargs)
    with Session(engine) as db:
        with monkeypatch.context() as patch:
            patch.setattr(cls, method, fail_after_first_write)
            with pytest.raises(RuntimeError, match="PostgreSQL injected failure"):
                load_wigger_demo(db)
        assert [db.scalar(select(func.count()).select_from(model)) for model in
                (CaseModel, SamplingSiteModel, CandidateZoneModel, EvidenceItemModel)] == [0, 0, 0, 0]
        first = load_wigger_demo(db)
        assert load_wigger_demo(db).case_id == first.case_id


def test_postgresql_current_decisions_and_follow_up_preserve_history(postgres):
    engine, _ = postgres
    with Session(engine) as db:
        demo = load_wigger_demo(db)
        decision = evaluate_sampling_decision(demo.case_id, db, get_sampling_service(db))
        assert decision.status.value == "TIE"
        service = _service(db)
        first = service.reinvestigate(demo.case_id)
        assert first["compatibility"]["status"] == "COMPLETE"
        from app.repositories.follow_up_samples import FollowUpSampleRepository
        from app.services.follow_up_sample_service import FollowUpSampleService
        sample = FollowUpSampleService(FollowUpSampleRepository(db), get_sampling_service(db).hydrology_engine).create(
            demo.case_id, sampling_site_id=demo.detection_site_id,
            hyriv_id=20446064, sampled_at=datetime(2014, 6, 26),
            replicate_count=3, positive_replicates=0, assay="synthetic PostgreSQL regression",
            controls_status="PASS", collector_source="test", provenance={"synthetic": True},
        )
        second = service.reinvestigate(demo.case_id, trigger_follow_up_sample_id=sample.id)
        assert second["changed"]["overall"] is False
        assert second["compatibility"]["status"] == "COMPLETE"
        assert service.detail(demo.case_id, first["investigation_run_id"])["after"] == first["after"]


def test_additive_migration_does_not_trust_legacy_metadata(postgres):
    engine, migration = postgres
    with Session(engine) as db:
        original = load_wigger_demo(db)
        metadata = deepcopy(db.get(CaseModel, original.case_id).meta)
    command.downgrade(migration, "f1a2b3c4d5e6")
    command.upgrade(migration, "head")
    with Session(engine) as db:
        legacy = db.get(CaseModel, original.case_id)
        assert legacy.meta == metadata and legacy.reference_key is None
        assert OneHealthService(db).assess(legacy.id)["pathways"] == []
        current = load_wigger_demo(db)
        assert current.case_id != legacy.id
        assert db.get(CaseModel, legacy.id).meta == metadata
        assert OneHealthService(db).assess(current.case_id)["pathways"]


def test_postgresql_provider_failures_survive_session_restart(postgres):
    from app.context.service import ContextCollectionService
    from app.context.interfaces import ProviderResult
    from app.domain.enums import ContextProviderStatus
    from tests.unit.test_context_infrastructure import _request
    from unittest.mock import Mock
    engine,_=postgres
    with Session(engine) as db:
        demo=load_wigger_demo(db)
        provider=Mock();provider.name="synthetic PostgreSQL provider"
        provider.collect.return_value=ProviderResult(provider=provider.name,evidence_type="context_gbif_occurrence",
            status=ContextProviderStatus.ERROR,error="synthetic timeout",limitations=["Synthetic execution fixture"])
        result=ContextCollectionService(EvidenceRepository(db),[provider]).collect(demo.case_id,_request())[0]
        assert result["evidence_id"] is None
    with Session(engine) as db:
        previous=ContextCollectionService(EvidenceRepository(db),[]).get_context(demo.case_id)[0]
        assert previous["execution_id"]==result["execution_id"] and previous["error"]=="synthetic timeout"
        assert previous["status"]==ContextProviderStatus.ERROR
        assert db.scalar(select(func.count()).select_from(EvidenceItemModel))==4


def test_postgresql_candidate_follow_up_and_canonical_reinvestigation(postgres):
    from app.api.routes.sampling import persist_sampling_candidates
    from app.services.follow_up_sample_service import FollowUpSampleService
    from app.repositories.follow_up_samples import FollowUpSampleRepository
    from tests.unit.test_functional_completion import sample_payload
    engine,_=postgres
    with Session(engine) as db:
        demo=load_wigger_demo(db)
        sampling=get_sampling_service(db)
        candidate=persist_sampling_candidates(demo.case_id,db,sampling).candidates[0]
        sample=FollowUpSampleService(FollowUpSampleRepository(db),sampling.hydrology_engine).create(
            demo.case_id,**sample_payload(candidate_reference=f"HYRIV_ID:{candidate.hyriv_id}",reach=candidate.hyriv_id))
        assert sample.candidate_reference==str(candidate.site_id)
        first=_service(db).reinvestigate(demo.case_id)
        second=_service(db).reinvestigate(demo.case_id)
        assert first["scientific_result"]==second["scientific_result"]
        assert first["new_decision_id"]!=second["new_decision_id"]
        assert second["change_comparison_status"]=="AVAILABLE"


def test_detection_context_migration_backfills_legacy_without_inventing_observations(postgres):
    """Upgrade a populated pre-extension schema, preserving scientific snapshots."""
    from uuid import uuid4
    from datetime import date
    import sqlalchemy as sa
    from app.db.models import DetectionContextModel,TargetSpeciesModel,ReplicateObservationModel,SamplingDecisionModel
    engine,migration=postgres
    command.downgrade(migration,'c9d42e8a710f')
    case_id,site_id,evidence_id,decision_id=uuid4(),uuid4(),uuid4(),uuid4()
    snapshot={'candidates':[{'hyriv_id':20450127,'signature':[0,1,0],'pair_separation_score':2}]}
    stamp=datetime(2024,1,1)
    try:
        with engine.begin() as connection:
            meta=sa.MetaData()
            sites=sa.Table('sampling_sites',meta,autoload_with=connection)
            cases=sa.Table('cases',meta,autoload_with=connection)
            evidence=sa.Table('evidence_items',meta,autoload_with=connection)
            decisions=sa.Table('sampling_decisions',meta,autoload_with=connection)
            connection.execute(sites.insert().values(id=site_id,case_id=None,label='Legacy detection',latitude=47.3140004,longitude=7.8954007,
                hyriv_id=20446064,site_type='DETECTION_SITE',validation_status='MATCHED',meta={'source':'legacy record'}))
            connection.execute(cases.insert().values(id=case_id,target_taxon='Legacy taxon',observation_date=date(2014,6,25),
                detection_site_id=site_id,status='ACTIVE',created_at=stamp,updated_at=stamp,meta={'name':'Legacy migration test'}))
            connection.execute(sites.update().where(sites.c.id==site_id).values(case_id=case_id))
            connection.execute(evidence.insert().values(id=evidence_id,case_id=case_id,evidence_type='edna_observation',source='Original laboratory record',
                value={'replicate_results':['Positive','Negative']},provenance={'original':True},created_at=stamp))
            connection.execute(evidence.insert().values(id=uuid4(),case_id=case_id,evidence_type='historical_edna_measurement',source='Original historical record',
                value={'concentration':12},provenance={'original':True},created_at=stamp))
            connection.execute(evidence.insert().values(id=uuid4(),case_id=case_id,evidence_type='edna_observation',source='Incomplete legacy observation',
                value={'replicate_results':['Positive',None]},provenance={'original':True},created_at=stamp))
            connection.execute(decisions.insert().values(id=decision_id,case_id=case_id,candidate_scope='REGISTERED_SITES',
                candidate_snapshot=snapshot,status='TIE',recommended_site_ids=[],rationale='Original decision',created_at=stamp))
    finally:command.upgrade(migration,'head')
    with Session(engine) as db:
        context=db.scalar(select(DetectionContextModel).where(DetectionContextModel.case_id==case_id))
        assert context.is_primary and context.site_id==site_id and context.sampled_on==date(2014,6,25)
        assert db.get(TargetSpeciesModel,context.species_id).taxon=='Legacy taxon'
        assert db.get(EvidenceItemModel,evidence_id).detection_context_id==context.id
        observations=list(db.scalars(select(ReplicateObservationModel).order_by(ReplicateObservationModel.replicate_index)))
        assert [row.result for row in observations]==['Positive','Negative']
        assert all(row.evidence_id==evidence_id for row in observations)
        decision=db.get(SamplingDecisionModel,decision_id)
        assert decision.candidate_snapshot==snapshot and decision.created_at==stamp and decision.rationale=='Original decision'
        assert decision.detection_context_id==context.id


def test_postgresql_detection_context_isolation_and_foreign_keys(postgres):
    from app.db.models import DetectionContextModel,TargetSpeciesModel,ReplicateObservationModel
    from app.repositories.detection_contexts import detection_scope
    from tests.unit.test_detection_contexts import extra,observe
    from sqlalchemy.exc import IntegrityError
    engine,_=postgres
    with Session(engine) as db:
        demo=load_wigger_demo(db)
        other=extra(db,demo.case_id)
        observe(db,demo.case_id,other,['Negative','Positive'])
        with detection_scope(db,other['id']):
            records=EvidenceRepository(db).get_evidence_by_case(demo.case_id)
            assert len(records)==1 and records[0].value['replicate_results']==['Negative','Positive']
            assert SamplingRepository(db).get_zones_by_case(demo.case_id)==[]
        assert len(EvidenceRepository(db).get_evidence_by_case(demo.case_id))==4
        from tests.unit.test_wigger_workflow_repairs import create
        second_case=create(db)
        foreign_species=db.scalar(select(TargetSpeciesModel).where(TargetSpeciesModel.case_id==second_case.id))
        db.add(DetectionContextModel(case_id=demo.case_id,species_id=foreign_species.id,
            site_id=demo.detection_site_id,sampled_on=datetime(2024,1,1).date(),event_label='Invalid ownership'))
        with pytest.raises(IntegrityError):db.commit()
        db.rollback()
