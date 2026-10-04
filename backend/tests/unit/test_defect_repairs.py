"""Boundary, identity, version and migration regressions; frozen science is unchanged."""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError
from sqlalchemy import create_engine, text

from app.api.routes.demo import load_wigger_demo
from app.api.routes.sampling import (
    create_candidate_zone, evaluate_sampling_decision, generate_sampling_candidates,
    get_decision_trace, get_sampling_service, persist_sampling_candidates,
)
from app.db.session import get_db
from app.domain.enums import ValidationStatus
from app.main import app
from app.repositories.sampling import SamplingRepository
from app.schemas.sampling import CandidateZoneCreateRequest
from app.services.investigation_service import InvestigationService
from app.services.sampling_service import SamplingService
from tests.unit.test_investigation_runs import _service, FailingDecisionEngine
from tests.unit.test_case_creation_integration import _post_json


def zone_request(root, members):
    return {"label": "Regression zone", "root_hyriv_id": root,
            "reach_ids": members, "validation_status": "NOT_VERIFIED"}


@pytest.mark.parametrize("root,members", [(1, [1, 1]), (1, [2]), (1, [1, 0]),
                                           (1, [1, -2]), (1, [1, 2.5]), (1, [])])
def test_zone_schema_rejects_invalid_members(root, members):
    with pytest.raises(ValidationError):
        CandidateZoneCreateRequest(**zone_request(root, members))


@pytest.fixture
def api(db_session):
    service = _service(db_session)
    sampling = SamplingService(SamplingRepository(db_session), service.sampling_engine,
                               service.candidate_generator.hydrology_engine,
                               service.candidate_generator, service.site_a_fraction)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_sampling_service] = lambda: sampling
    try:
        yield _post_json, sampling
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("root,members,status", [
    (20450127, [20450127, 999999999], 404),
    (20450127, [20450127, 20451169], 422),
    (999999999, [999999999], 404),
    (20450127, [20450127, 20450127], 422),
    (20450127, [20451169], 422),
])
def test_zone_api_errors(db_session, api, root, members, status):
    case_id = load_wigger_demo(db_session).case_id
    client, _ = api
    count = len(SamplingRepository(db_session).get_zones_by_case(case_id))
    status_code, response = client(f"/cases/{case_id}/zones", zone_request(root, members))
    assert status_code == status, response
    assert response.get("detail")
    assert len(SamplingRepository(db_session).get_zones_by_case(case_id)) == count


def test_zone_rejects_missing_case_and_accepts_connected_members(db_session, api):
    client, _ = api
    payload = zone_request(20450127, [20450127])
    assert client(f"/cases/{uuid4()}/zones", payload)[0] == 404
    case_id = load_wigger_demo(db_session).case_id
    assert client(f"/cases/{case_id}/zones", payload)[0] == 201


def test_zone_rejects_omitted_connecting_reaches(db_session):
    case_id = load_wigger_demo(db_session).case_id
    class Network:
        def get_reach(self, reach):
            return reach
        def get_downstream_path(self, start, root):
            return [start, 2, root]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        create_candidate_zone(case_id, CandidateZoneCreateRequest(**zone_request(3, [1, 3])),
                              db_session, SimpleNamespace(hydrology_engine=Network()))
    assert error.value.status_code == 422
    assert "connecting reaches" in error.value.detail["message"]


def test_generated_identity_scope_and_frozen_registered_tie(db_session, api):
    case_id = load_wigger_demo(db_session).case_id
    _, sampling = api
    repository = SamplingRepository(db_session)
    generated = generate_sampling_candidates(case_id, db_session, sampling)
    ids = [candidate.site_id for candidate in generated.candidates]
    from app.db.models import SamplingSiteModel
    assert db_session.query(SamplingSiteModel).count() == 4
    persisted = persist_sampling_candidates(case_id, db_session, sampling)
    assert [candidate.site_id for candidate in persisted.candidates] == ids
    persist_sampling_candidates(case_id, db_session, sampling)
    assert db_session.query(SamplingSiteModel).count() == 4 + len(ids)
    assert all(repository.get_site_by_id(site_id).role == "GENERATED_REPRESENTATIVE" for site_id in ids)
    assert len(repository.get_sites_by_case(case_id)) == 4
    first = _service(db_session).reinvestigate(case_id)
    second = _service(db_session).reinvestigate(case_id)
    assert [item["site_id"] for item in first["candidate_generation"]["candidates"]] == [str(value) for value in ids]
    assert first["sampling_decision"]["candidate_scope"] == "GENERATED_REPRESENTATIVES"
    assert first["decision_trace"]["decision_id"] == first["new_decision_id"]
    assert not second["changed"]["overall"]
    assert all(repository.get_site_by_id(value) for value in
               repository.get_decision_by_id(first["new_decision_id"]).recommended_site_ids)
    historical = _service(db_session).detail(case_id, first["investigation_run_id"])
    assert historical["before"] == {}
    decision = evaluate_sampling_decision(case_id, db_session, sampling)
    assert decision.status.value == "TIE"
    assert [repository.get_site_by_id(value).label for value in decision.recommended_site_ids] == ["Site B", "Site C", "Site D"]
    assert decision.candidate_scope == "REGISTERED_SITES"
    assert [item["label"] for item in decision.candidate_snapshot["candidates"]] == ["Site A (S1)", "Site B", "Site C", "Site D"]
    trace = get_decision_trace(case_id, db_session, decision_id=first["new_decision_id"])
    assert trace.decision_id == first["new_decision_id"]


def test_failed_run_does_not_leave_registered_or_generated_candidates(db_session):
    case_id = load_wigger_demo(db_session).case_id
    from sqlalchemy import func, select
    from app.db.models import SamplingSiteModel
    before = db_session.scalar(select(func.count()).select_from(SamplingSiteModel))
    with pytest.raises(RuntimeError, match="injected decision failure"):
        _service(db_session, FailingDecisionEngine()).reinvestigate(case_id)
    assert db_session.scalar(select(func.count()).select_from(SamplingSiteModel)) == before


def test_decision_comparison_detects_changed_winners_and_scope():
    original = {"status": "TIE", "rationale": "same", "recommended_site_ids": ["a"],
                "candidate_scope": "REGISTERED_SITES"}
    for modified in ({**original, "recommended_site_ids": ["b"]},
                     {**original, "candidate_scope": "GENERATED_REPRESENTATIVES"}):
        assert InvestigationService._decision_signature(original) != InvestigationService._decision_signature(modified)


def test_environment_configuration_is_honored(tmp_path):
    backend_dir = str(Path(__file__).resolve().parents[2])
    env = {**os.environ, "DATABASE_URL": "sqlite:///:memory:", "PREFLIGHT_DATA_DIR": str(tmp_path),
           "CARRARO_DATA_DIR": str(tmp_path), "DEBUG": "false", "PORT": "8123",
           "PYTHONPATH": backend_dir}
    result = subprocess.run([sys.executable, "-c", "from config import config; config.validate(); "
                             "assert config.DATABASE_URL == 'sqlite:///:memory:'; "
                             "assert config.PORT == 8123 and config.DEBUG is False; "
                             "assert str(config.PREFLIGHT_DATA_DIR) == " + repr(str(tmp_path))],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_migration_changes_only_decision_metadata_and_reverses():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/f1a2b3c4d5e6_decision_candidate_scope.py"
    spec = importlib.util.spec_from_file_location("scope_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE sampling_decisions (id TEXT PRIMARY KEY, status TEXT, rationale TEXT)"))
        connection.execute(text("CREATE TABLE investigation_runs (new_decision_id TEXT)"))
        connection.execute(text("CREATE TABLE observations (value TEXT)"))
        connection.execute(text("INSERT INTO observations VALUES ('frozen')"))
        connection.execute(text("INSERT INTO sampling_decisions VALUES ('registered', 'TIE', 'unchanged'), ('generated', 'TIE', 'unchanged')"))
        connection.execute(text("INSERT INTO investigation_runs VALUES ('generated')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
            assert connection.execute(text("SELECT id, candidate_scope FROM sampling_decisions ORDER BY id")).all() == [
                ("generated", "GENERATED_REPRESENTATIVES"), ("registered", "REGISTERED_SITES")]
            assert connection.execute(text("SELECT status, rationale FROM sampling_decisions")).all() == [("TIE", "unchanged")] * 2
            assert connection.execute(text("SELECT value FROM observations")).scalar() == "frozen"
            migration.downgrade()
        assert [row[1] for row in connection.execute(text("PRAGMA table_info(sampling_decisions)"))] == ["id", "status", "rationale"]


def test_manual_hypotheses_cannot_claim_verified(db_session, api):
    case_id = load_wigger_demo(db_session).case_id
    client, _ = api
    payload = {**zone_request(20450127, [20450127]), "validation_status": "VERIFIED"}
    assert client(f"/cases/{case_id}/zones", payload)[0] == 422


def test_wigger_reference_import_is_atomic_idempotent_and_preserves_manual_evidence(db_session):
    from app.api.routes.demo import reuse_wigger_reference
    from tests.unit.test_case_creation_integration import _creation_with_replicates, _hydrology
    from app.api.routes.cases import create_case
    from app.repositories.cases import CaseRepository
    from app.repositories.evidence import EvidenceRepository
    from app.services.case_service import CaseService
    from fastapi import HTTPException
    request = _creation_with_replicates()
    case = create_case(request, db_session, CaseService(CaseRepository(db_session)), _hydrology())
    repo = SamplingRepository(db_session)
    reuse_wigger_reference(db_session, case.id)
    ids = [zone.id for zone in repo.get_zones_by_case(case.id)]
    reuse_wigger_reference(db_session, case.id)
    assert [zone.id for zone in repo.get_zones_by_case(case.id)] == ids
    assert len(repo.get_sites_by_case(case.id)) == 4
    assert all(zone.validation_status.value == "VERIFIED" for zone in repo.get_zones_by_case(case.id))
    assert repo.get_site_by_id(case.detection_site_id).validation_status.value == "MATCHED"
    assert len(EvidenceRepository(db_session).get_evidence_by_case(case.id)) == 1
    other = create_case(request.model_copy(update={"detection_site_hyriv_id": 20450127}), db_session,
                        CaseService(CaseRepository(db_session)), _hydrology())
    with pytest.raises(HTTPException, match="") as error:
        reuse_wigger_reference(db_session, other.id)
    assert error.value.status_code == 422
    assert repo.get_zones_by_case(other.id) == []
    manual = create_case(request, db_session, CaseService(CaseRepository(db_session)), _hydrology())
    repo.create_zone(manual.id, "Z1", 20447392, [20447392],
                            ValidationStatus.NOT_VERIFIED)
    with pytest.raises(HTTPException) as error:
        reuse_wigger_reference(db_session, manual.id)
    assert error.value.status_code == 409
    assert repo.get_zones_by_case(manual.id)[0].validation_status.value == "NOT_VERIFIED"
    assert len(repo.get_sites_by_case(manual.id)) == 1


def test_wigger_reference_rejects_changed_provenance(tmp_path):
    import shutil
    from config import config
    from app.scientific.data_loader import WiggerPreflightLoader
    shutil.copytree(config.PREFLIGHT_DATA_DIR, tmp_path / "reference")
    loader = WiggerPreflightLoader(tmp_path / "reference")
    loader.validate_frozen_reference()
    (tmp_path / "reference" / "candidate_zones_real.geojson").write_text('{}')
    with pytest.raises(ValueError, match="provenance mismatch"):
        loader.validate_frozen_reference()


def test_reference_import_failure_rolls_back_all_new_rows(db_session, monkeypatch):
    from app.api.routes.demo import reuse_wigger_reference
    from tests.unit.test_case_creation_integration import _creation_with_replicates, _hydrology
    from app.api.routes.cases import create_case
    from app.repositories.cases import CaseRepository
    from app.services.case_service import CaseService
    case = create_case(_creation_with_replicates(), db_session,
                       CaseService(CaseRepository(db_session)), _hydrology())
    def fail(*args, **kwargs):
        raise RuntimeError("reference site failed")
    monkeypatch.setattr(SamplingRepository, "create_site", fail)
    with pytest.raises(RuntimeError, match="reference site failed"):
        reuse_wigger_reference(db_session, case.id)
    repo = SamplingRepository(db_session)
    assert repo.get_zones_by_case(case.id) == []
    assert len(repo.get_sites_by_case(case.id)) == 1


def test_generated_candidate_identifiers_are_case_specific():
    first, second = uuid4(), uuid4()
    assert SamplingRepository.generated_site_id(first, 20450127) == SamplingRepository.generated_site_id(first, 20450127)
    assert SamplingRepository.generated_site_id(first, 20450127) != SamplingRepository.generated_site_id(second, 20450127)
