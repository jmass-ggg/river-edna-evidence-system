from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.api.routes.cases import create_case
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
