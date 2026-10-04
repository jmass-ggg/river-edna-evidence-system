import asyncio
import json
from datetime import date, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.api.dependencies import get_hydrology_engine
from app.api.routes.cases import create_case, get_case_service
from app.api.routes.sampling import get_investigation_map, get_sampling_service
from app.db.session import get_db
from app.main import app
from app.repositories.cases import CaseRepository
from app.repositories.sampling import SamplingRepository
from app.db.models import SamplingSiteModel
from app.schemas.cases import CaseCreateRequest
from app.services.case_service import CaseService
from app.scientific.data_loader import WiggerPreflightLoader
from app.scientific.hydrology.engine import HydrologyEngine
from config import config


def _hydrology():
    loader = WiggerPreflightLoader(config.PREFLIGHT_DATA_DIR)
    return HydrologyEngine(loader.load_reaches(), loader.load_edges())


def _post_json(path, payload, method="POST"):
    request_body = json.dumps(payload).encode()
    request_sent = False
    messages = []

    async def receive():
        nonlocal request_sent
        if request_sent:
            return {"type": "http.disconnect"}
        request_sent = True
        return {"type": "http.request", "body": request_body, "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"content-type", b"application/json")],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "root_path": "",
    }
    asyncio.run(app(scope, receive, send))
    status_code = next(
        message["status"] for message in messages if message["type"] == "http.response.start"
    )
    body = b"".join(
        message.get("body", b"")
        for message in messages
        if message["type"] == "http.response.body"
    )
    return status_code, json.loads(body)


def test_created_detection_site_is_returned_by_case_scoped_site_query(db_session):
    request = CaseCreateRequest(
        target_taxon="Test taxon",
        observation_date=date(2026, 10, 2),
        detection_site_latitude=47.314,
        detection_site_longitude=7.8954,
        detection_site_hyriv_id=20446064,
        metadata={"name": "Creation integration"},
    )

    case = create_case(
        request=request,
        db=db_session,
        case_service=CaseService(CaseRepository(db_session)),
        hydrology_engine=_hydrology(),
    )
    sites = SamplingRepository(db_session).get_sites_by_case(case.id)

    assert len(sites) == 1
    assert sites[0].id == case.detection_site_id
    assert sites[0].case_id == case.id

    map_response = get_investigation_map(
        case.id, db=db_session, sampling_service=get_sampling_service(db_session)
    )
    assert map_response.available is True
    assert map_response.source_zones["features"] == []
    assert len(map_response.sites) == 1
    assert map_response.sites[0].latitude == request.detection_site_latitude
    assert map_response.sites[0].longitude == request.detection_site_longitude
    assert any(
        int(feature["properties"]["HYRIV_ID"]) == request.detection_site_hyriv_id
        for feature in map_response.river_network["features"]
    )


def test_post_cases_returns_201_and_persists_complete_investigation(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_case_service] = lambda: CaseService(
        CaseRepository(db_session)
    )
    app.dependency_overrides[get_hydrology_engine] = _hydrology

    try:
        status_code, body = _post_json(
            "/cases",
            {
                "target_taxon": "Fredericella sultana",
                "observation_date": "2014-06-25",
                "detection_site_latitude": 47.31400039098192,
                "detection_site_longitude": 7.895400745863826,
                "detection_site_hyriv_id": 20446064,
                "metadata": {
                    "name": "Wigger River Investigation Test",
                    "additional_metadata": "",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert status_code == 201
    case = CaseRepository(db_session).get_case_by_id(UUID(body["id"]))
    sites = SamplingRepository(db_session).get_sites_by_case(case.id)
    assert body["target_taxon"] == "Fredericella sultana"
    assert body["detection_site_id"] == str(case.detection_site_id)
    assert len(sites) == 1
    assert sites[0].id == case.detection_site_id


def test_failed_case_creation_rolls_back_detection_site(db_session):
    class FailingCaseService:
        def create_case(self, **kwargs):
            raise RuntimeError("simulated case insert failure")

    request = CaseCreateRequest(
        target_taxon="Test taxon",
        observation_date=date(2026, 10, 2),
        detection_site_latitude=47.314,
        detection_site_longitude=7.8954,
        detection_site_hyriv_id=20446064,
    )

    with pytest.raises(RuntimeError, match="simulated case insert failure"):
        create_case(
            request=request,
            db=db_session,
            case_service=FailingCaseService(),
            hydrology_engine=_hydrology(),
        )

    assert CaseRepository(db_session).list_cases() == []
    assert db_session.query(SamplingSiteModel).count() == 0


def test_case_creation_rejects_unknown_hydrorivers_reach_without_writes(
    db_session,
):
    request = CaseCreateRequest(
        target_taxon="Test taxon",
        observation_date=date(2026, 10, 2),
        detection_site_latitude=47.314,
        detection_site_longitude=7.8954,
        detection_site_hyriv_id=999999999,
        metadata={"name": "Invalid reach"},
    )

    try:
        create_case(
            request=request,
            db=db_session,
            case_service=CaseService(CaseRepository(db_session)),
            hydrology_engine=_hydrology(),
        )
    except ValueError as error:
        assert "not found in loaded network data" in str(error)
    else:
        raise AssertionError("Unknown reach was accepted")

    assert CaseRepository(db_session).list_cases() == []
    assert db_session.query(SamplingSiteModel).count() == 0


def test_case_schema_rejects_future_observation_date():
    with pytest.raises(ValidationError, match="cannot be in the future"):
        CaseCreateRequest(
            target_taxon="Test taxon",
            observation_date=date.today() + timedelta(days=1),
            detection_site_latitude=47.314,
            detection_site_longitude=7.8954,
            detection_site_hyriv_id=20446064,
        )


def _creation_with_replicates():
    return CaseCreateRequest(
        target_taxon="Manual demonstration", observation_date=date(2026, 10, 2),
        detection_site_latitude=47.3140004, detection_site_longitude=7.8954007,
        detection_site_hyriv_id=20446064,
        initial_evidence=[{"evidence_type": "edna_observation", "source": "recorded assay",
                           "value": {"replicate_results": ["Positive", "Negative", "Invalid"], "assay_metadata": "Assay X"},
                           "provenance": {"entry_method": "manual"}}],
    )


def test_initial_evidence_stores_exact_replicates_atomically(db_session):
    from app.repositories.evidence import EvidenceRepository
    case = create_case(_creation_with_replicates(), db_session,
                       CaseService(CaseRepository(db_session)), _hydrology())
    evidence = EvidenceRepository(db_session).get_evidence_by_case(case.id)
    assert len(evidence) == 1
    assert evidence[0].value == {"replicate_results": ["Positive", "Negative", "Invalid"], "assay_metadata": "Assay X"}


def test_initial_evidence_failure_rolls_back_and_retry_creates_one_case(db_session, monkeypatch):
    from app.repositories.evidence import EvidenceRepository
    original = EvidenceRepository.add_evidence
    def fail(*args, **kwargs):
        raise RuntimeError("evidence insert failed")
    monkeypatch.setattr(EvidenceRepository, "add_evidence", fail)
    with pytest.raises(RuntimeError, match="evidence insert failed"):
        create_case(_creation_with_replicates(), db_session,
                    CaseService(CaseRepository(db_session)), _hydrology())
    assert CaseRepository(db_session).list_cases() == []
    assert db_session.query(SamplingSiteModel).count() == 0
    monkeypatch.setattr(EvidenceRepository, "add_evidence", original)
    create_case(_creation_with_replicates(), db_session,
                CaseService(CaseRepository(db_session)), _hydrology())
    assert len(CaseRepository(db_session).list_cases()) == 1


@pytest.mark.parametrize("results", [[], ["Unknown"], ["Positive", ""]])
def test_initial_replicate_validation_rejects_unrecorded_results(results):
    payload = _creation_with_replicates().model_dump()
    payload["initial_evidence"][0]["value"]["replicate_results"] = results
    with pytest.raises(ValidationError, match="recorded"):
        CaseCreateRequest(**payload)


def test_evidence_without_replicate_results_retains_existing_flexible_contract():
    from app.schemas.evidence import EvidenceCreateRequest
    request = EvidenceCreateRequest(evidence_type="edna_observation", source="existing source", value={"detected": True})
    assert request.value == {"detected": True}
