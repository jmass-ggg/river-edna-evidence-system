from datetime import date, datetime
from unittest.mock import Mock

from app.context.interfaces import ContextRequest, ProviderResult
from app.context.providers.gbif import GbifOccurrenceProvider
from app.context.providers.urbanization import UrbanizationProvider
from app.context.providers.weather import HistoricalWeatherProvider
from app.context.service import ContextCollectionService
from app.db.models import CaseModel, SamplingSiteModel
from app.domain.enums import (
    CaseStatus,
    ContextProviderStatus,
    EvidenceCompatibility,
    EvidenceStrength,
    SiteType,
    ValidationStatus,
)
from app.repositories.evidence import EvidenceRepository


def _case(db_session):
    site = SamplingSiteModel(
        label="A", latitude=47.0, longitude=8.0, hyriv_id=20446064,
        site_type=SiteType.DETECTION_SITE.value,
        validation_status=ValidationStatus.VERIFIED.value, meta={},
    )
    db_session.add(site)
    db_session.flush()
    case = CaseModel(
        target_taxon="Test taxon", observation_date=date(2024, 1, 3),
        detection_site_id=site.id, status=CaseStatus.ACTIVE.value, meta={},
    )
    db_session.add(case)
    db_session.commit()
    return case


def _request():
    return ContextRequest("Test taxon", 47.0, 8.0, date(2024, 1, 3), 1000, 1)


def test_gbif_parses_compact_occurrences_with_provenance():
    client = Mock()
    client.get_json.return_value = {
        "count": 1,
        "endOfRecords": True,
        "results": [{
            "key": 42, "decimalLatitude": 47.1, "decimalLongitude": 8.1,
            "eventDate": "2020-01-01", "datasetKey": "dataset-1",
            "ignored_large_field": "not stored",
        }],
    }
    result = GbifOccurrenceProvider(client).collect(_request())

    assert result.status == ContextProviderStatus.SUCCESS
    assert result.data["count"] == 1
    assert result.data["radius_m"] == 1000
    assert result.data["occurrences"] == [{
        "occurrence_id": 42, "latitude": 47.1, "longitude": 8.1,
        "date": "2020-01-01", "dataset_id": "dataset-1",
    }]
    assert result.provenance["endpoint"].endswith("/occurrence/search")
    assert "geometry" in client.get_json.call_args.args[1]


def test_urbanization_and_weather_preserve_temporal_context():
    urban_client = Mock()
    urban_client.query.return_value = {
        "built_up_metric": 0.4, "source_year": 2015, "resolution": "100 m",
        "source_version": "GHSL-test", "temporal_alignment": "nearest prior epoch",
        "provenance": {"dataset": "fixture"},
    }
    weather_client = Mock()
    weather_client.query.return_value = {
        "temperature": {"mean_c": 12.0}, "precipitation": {"total_mm": 4.0},
        "source_model": "fixture model", "provenance": {"dataset": "fixture"},
    }

    urban = UrbanizationProvider(urban_client).collect(_request())
    weather = HistoricalWeatherProvider(weather_client).collect(_request())

    assert urban.data["temporal_alignment"] == "nearest prior epoch"
    assert urban.data["source_year"] == 2015
    assert weather.data["requested_window"] == {
        "start": "2024-01-02", "end": "2024-01-04"
    }
    assert weather.data["source_model"] == "fixture model"


def test_provider_failure_isolated_and_context_is_uninterpreted(db_session):
    case = _case(db_session)
    failed = Mock(name="failed provider")
    failed.name = "failed provider"
    failed.collect.side_effect = RuntimeError("provider down")
    successful = Mock(name="working provider")
    successful.name = "working provider"
    successful.collect.return_value = ProviderResult(
        provider="working provider", evidence_type="context_urbanization",
        status=ContextProviderStatus.SUCCESS,
        data={"temporal_alignment": "mismatch stored"},
        provenance={"fixture": True},
    )
    service = ContextCollectionService(EvidenceRepository(db_session), [failed, successful])

    outcomes = service.collect(case.id, _request())

    assert [item["status"] for item in outcomes] == [
        ContextProviderStatus.ERROR, ContextProviderStatus.SUCCESS
    ]
    assert outcomes[1]["compatibility"] == EvidenceCompatibility.UNKNOWN
    assert outcomes[1]["strength"] == EvidenceStrength.UNASSESSED
    stored = service.get_context(case.id)
    assert len(stored) == 1
    assert stored[0]["data"]["temporal_alignment"] == "mismatch stored"


def test_context_providers_only_receive_injected_clients():
    assert GbifOccurrenceProvider(Mock()).http_client is not None
    assert UrbanizationProvider(Mock()).client is not None
    assert HistoricalWeatherProvider(Mock()).client is not None
