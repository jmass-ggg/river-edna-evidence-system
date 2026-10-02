from sqlalchemy import func, select

from app.api.routes.demo import load_wigger_demo
from app.db.models import (
    GeneratedCandidateSnapshotModel, HypothesisStateModel, InvestigationRunModel,
    SamplingDecisionModel,
)
from app.domain.enums import HypothesisStatus, InvestigationRunStatus
from app.main import app
from app.repositories.investigations import InvestigationRepository
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.scientific.hydrology.engine import HydrologyEngine
from app.scientific.hypothesis import ConservativeHypothesisStateResolver
from app.scientific.sampling.candidate_generator import CandidateSiteGenerator
from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine
from app.services.investigation_service import InvestigationService
from config import config


def _service(db_session, sampling_engine=None):
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    hydrology = HydrologyEngine(loader.load_reaches(), loader.load_edges())
    coordinates = {}
    for _, row in loader.load_reach_geometries().iterrows():
        midpoint = row.geometry.interpolate(0.5, normalized=True)
        coordinates[int(row.HYRIV_ID)] = (midpoint.y, midpoint.x)
    generator = CandidateSiteGenerator(hydrology, coordinates)
    fraction = loader.load_site_a_snap_validation()["snapped_coordinate"]["fraction_along_reach"]
    return InvestigationService(
        db_session, EvidenceCompatibilityEngineImpl(), ConservativeHypothesisStateResolver(),
        generator, sampling_engine or ScaffoldSamplingDecisionEngine(), fraction,
    )


def test_reinvestigation_persists_append_only_history(db_session):
    case_id = load_wigger_demo(db_session).case_id
    service = _service(db_session)

    first = service.reinvestigate(case_id)
    second = service.reinvestigate(case_id)
    runs = service.list(case_id)

    assert len(runs) == 2
    assert first["investigation_run_id"] != second["investigation_run_id"]
    assert all(run["status"] == InvestigationRunStatus.COMPLETED.value for run in runs)
    assert second["previous_decision_id"] == first["new_decision_id"]
    assert second["changed"] == {
        "hypotheses_changed": False,
        "candidates_changed": False,
        "decision_changed": False,
        "overall": False,
    }
    assert db_session.scalar(select(func.count()).select_from(HypothesisStateModel)) == 6
    assert db_session.scalar(select(func.count()).select_from(GeneratedCandidateSnapshotModel)) == 8
    states = db_session.scalars(select(HypothesisStateModel)).all()
    assert all(state.status == HypothesisStatus.UNKNOWN.value for state in states)
    assert all("No validated" in state.reason for state in states)
    assert len(first["candidate_generation"]["candidates"]) == 4


class FailingDecisionEngine(ScaffoldSamplingDecisionEngine):
    def make_recommendation(self, evaluations):
        raise RuntimeError("injected decision failure")


def test_failed_run_rolls_back_results_and_preserves_previous_decision(db_session):
    case_id = load_wigger_demo(db_session).case_id
    successful = _service(db_session).reinvestigate(case_id)
    decisions_before = db_session.scalar(select(func.count()).select_from(SamplingDecisionModel))
    states_before = db_session.scalar(select(func.count()).select_from(HypothesisStateModel))

    try:
        _service(db_session, FailingDecisionEngine()).reinvestigate(case_id)
    except RuntimeError as exc:
        assert str(exc) == "injected decision failure"
    else:
        raise AssertionError("failure was not propagated")

    assert db_session.scalar(select(func.count()).select_from(SamplingDecisionModel)) == decisions_before
    assert db_session.scalar(select(func.count()).select_from(HypothesisStateModel)) == states_before
    runs = InvestigationRepository(db_session).list_for_case(case_id)
    assert runs[-1].status == InvestigationRunStatus.FAILED.value
    assert runs[-1].failure_reason == "injected decision failure"
    assert runs[-1].previous_decision_id == successful["new_decision_id"]
    assert runs[-1].new_decision_id is None


def test_reinvestigation_api_contract_is_exposed():
    paths = app.openapi()["paths"]
    assert "/cases/{case_id}/reinvestigate" in paths
    assert "/cases/{case_id}/investigation-runs" in paths
    assert "/cases/{case_id}/investigation-runs/{run_id}" in paths
