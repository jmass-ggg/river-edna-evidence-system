from datetime import date, datetime
from uuid import uuid4

import pytest

from app.context.interfaces import ContextRequest
from app.context.providers.gbif import GbifOccurrenceProvider
from app.context.providers.urbanization import UrbanizationProvider
from app.context.providers.weather import HistoricalWeatherProvider
from app.db.models import CaseModel, SamplingSiteModel
from app.domain.enums import (
    CaseStatus,
    EvidenceCompatibility,
    EvidenceStrength,
    OneHealthClaimStatus,
    SiteType,
    ValidationStatus,
)
from app.domain.models import Case, CandidateZone, EvidenceItem
from app.repositories.evidence import EvidenceRepository
from app.scientific.evidence.engine import EvidenceCompatibilityEngineImpl
from app.services.one_health_service import FRAMEWORK, OneHealthService


def _domain_case_and_zone():
    case_id = uuid4()
    case = Case(
        id=case_id, target_taxon="Fredericella sultana",
        observation_date=date(2014, 6, 25), detection_site_id=uuid4(),
        status=CaseStatus.ACTIVE, created_at=datetime.now(), updated_at=datetime.now(),
    )
    zone = CandidateZone(
        id=uuid4(), case_id=case_id, label="Z1", root_hyriv_id=1,
        reach_ids=[1], validation_status=ValidationStatus.VERIFIED,
    )
    return case, zone


@pytest.mark.parametrize("evidence_type", [
    "context_gbif_occurrence",
    "context_urbanization",
    "context_historical_weather",
    "follow_up_edna_sample",
])
def test_v3_evidence_types_remain_unknown_and_unassessed(evidence_type):
    case, zone = _domain_case_and_zone()
    evidence = EvidenceItem(
        id=uuid4(), case_id=case.id, evidence_type=evidence_type,
        source="fixture", value={}, observed_at=None, quality=None,
        provenance={"fixture": True}, created_at=datetime.now(),
    )

    result = EvidenceCompatibilityEngineImpl().assess_evidence_for_zone(
        case, zone, [evidence], []
    )[0]

    assert result.compatibility == EvidenceCompatibility.UNKNOWN
    assert result.strength == EvidenceStrength.UNASSESSED
    assert result.rule_id is None
    assert result.strength_rule_id is None


@pytest.fixture
def wigger_fs_case(db_session):
    site = SamplingSiteModel(
        label="Site A (S1)", latitude=47.0, longitude=8.0, hyriv_id=20446064,
        site_type=SiteType.DETECTION_SITE.value,
        validation_status=ValidationStatus.MATCHED.value, meta={},
    )
    db_session.add(site)
    db_session.flush()
    case = CaseModel(
        target_taxon="Fredericella sultana", observation_date=date(2014, 6, 25),
        detection_site_id=site.id, status=CaseStatus.ACTIVE.value,
        meta={
            "historical_observation": {
                "station": "S1", "species": "Fredericella sultana",
                "date": "2014-06-25", "state": "DETECTED",
                "observation_index": 4, "concentration_mol_l": 1.29832198e-17,
                "provenance": {"date_variable": "Date.S1", "concentration_variable": "Fs.S1"},
            }
        },
    )
    db_session.add(case)
    db_session.commit()
    return case


def test_fs_pathway_preserves_supported_and_unknown_claims(db_session, wigger_fs_case):
    response = OneHealthService(db_session).assess(wigger_fs_case.id)
    pathway = response["pathways"][0]

    assert response["framework"] == FRAMEWORK
    assert pathway["monitoring_finding"]["status"] == OneHealthClaimStatus.OBSERVED
    assert pathway["ecological_relevance"]["status"] == OneHealthClaimStatus.SUPPORTED_RELATIONSHIP
    assert pathway["animal_health_relevance"]["status"] == OneHealthClaimStatus.SUPPORTED_RELATIONSHIP
    assert pathway["community_management_relevance"]["status"] == OneHealthClaimStatus.POSSIBLE_RELEVANCE
    assert pathway["parasite_presence"]["status"] == OneHealthClaimStatus.UNKNOWN
    assert pathway["fish_disease_status"]["status"] == OneHealthClaimStatus.UNKNOWN
    assert pathway["human_health_impact"]["status"] == OneHealthClaimStatus.UNKNOWN
    assert pathway["scientific_sources"]
    assert all(source["doi"] for source in pathway["scientific_sources"])
    assert pathway["provenance"]["historical_observation_provenance"]
    assert pathway["limitations"]


def test_temperature_context_does_not_create_disease_inference(db_session, wigger_fs_case):
    EvidenceRepository(db_session).add_evidence(
        case_id=wigger_fs_case.id,
        evidence_type="context_historical_weather",
        source="fixture weather",
        value={"temperature": {"mean_c": 18}, "precipitation": {"total_mm": 2}},
        provenance={"fixture": True},
    )

    pathway = OneHealthService(db_session).assess(wigger_fs_case.id)["pathways"][0]

    assert len(pathway["contextual_evidence"]) == 1
    assert pathway["contextual_evidence"][0]["status"] == OneHealthClaimStatus.OBSERVED
    assert pathway["parasite_presence"]["status"] == OneHealthClaimStatus.UNKNOWN
    assert pathway["fish_disease_status"]["status"] == OneHealthClaimStatus.UNKNOWN
    assert "disease_probability" not in pathway
    assert "risk_score" not in pathway


def test_context_language_does_not_overclaim():
    request = ContextRequest(
        "Fredericella sultana", 47.0, 8.0, date(2014, 6, 25), 1000
    )
    gbif_client = type("Gbif", (), {"get_json": lambda self, url, params: {
        "count": 0, "endOfRecords": True, "results": []
    }})()
    spatial = type("Spatial", (), {"query": lambda self, **kwargs: {
        "built_up_metric": 0.2, "source_year": 2014, "resolution": "100 m",
        "source_version": "fixture", "temporal_alignment": "same year",
        "temperature": {"mean_c": 10}, "precipitation": {"total_mm": 1},
        "source_model": "fixture", "provenance": {"fixture": True},
    }})()

    gbif = GbifOccurrenceProvider(gbif_client).collect(request)
    urban = UrbanizationProvider(spatial).collect(request)
    weather = HistoricalWeatherProvider(spatial).collect(request)

    assert any("do not prove current presence" in text for text in gbif.limitations)
    assert any("do not establish pollution, degradation, or health risk" in text for text in urban.limitations)
    assert any("does not diagnose or predict disease" in text for text in weather.limitations)
    assert any("does not prove eDNA transport" in text for text in weather.limitations)


def test_non_fs_case_has_framework_without_invented_pathway(db_session):
    site = SamplingSiteModel(
        label="A", latitude=0, longitude=0, hyriv_id=1,
        site_type=SiteType.DETECTION_SITE.value,
        validation_status=ValidationStatus.VERIFIED.value, meta={},
    )
    db_session.add(site)
    db_session.flush()
    case = CaseModel(
        target_taxon="Unreviewed taxon", observation_date=date(2024, 1, 1),
        detection_site_id=site.id, status=CaseStatus.ACTIVE.value, meta={},
    )
    db_session.add(case)
    db_session.commit()

    response = OneHealthService(db_session).assess(case.id)
    assert response["framework"] == FRAMEWORK
    assert response["pathways"] == []
