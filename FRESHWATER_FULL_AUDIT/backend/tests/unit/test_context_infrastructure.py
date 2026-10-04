from datetime import date, datetime
from unittest.mock import Mock

import pytest

from app.api.routes import context as context_routes
from app.context.interfaces import ContextRequest, ProviderResult
from app.context.providers.gbif import GbifOccurrenceProvider
from app.context.providers.urbanization import UrbanizationProvider
from app.context.providers.weather import HistoricalWeatherProvider, OpenMeteoHistoricalClient
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
from app.schemas.context import ContextCollectRequest


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


def _historical_request(window_days=0):
    # Exercise the Wigger observation date using fixture coordinates, not a site measurement.
    return ContextRequest("Test taxon", 47.0, 8.0, date(2014, 6, 25), 1000, window_days)


def _archive_payload():
    # Synthetic upstream response used solely to test the integration.
    return {
        "latitude": 47.0, "longitude": 8.0, "elevation": 848.0,
        "timezone": "GMT", "utc_offset_seconds": 0,
        "daily_units": {"time": "iso8601", "temperature_2m_mean": "°C", "precipitation_sum": "mm"},
        "daily": {
            "time": ["2014-06-25"], "temperature_2m_mean": [12.0], "precipitation_sum": [4.0],
        },
    }


def test_archive_integration_preserves_historical_source_and_resolution():
    http = Mock()
    http.get_json.return_value = _archive_payload()
    result = HistoricalWeatherProvider(OpenMeteoHistoricalClient(http)).collect(_historical_request())

    assert result.status == ContextProviderStatus.SUCCESS
    assert result.evidence_type == "context_historical_weather"
    assert result.data["requested_date"] == "2014-06-25"
    assert result.data["source_model"] == "ERA5"
    assert result.data["temperature"] == {
        "mean_c": 12.0, "unit": "°C", "daily": [{"date": "2014-06-25", "mean_c": 12.0}],
    }
    assert result.data["precipitation"]["total_mm"] == 4.0
    assert result.provenance["spatial_resolution"] == "0.25 degrees (approximately 25 km)"
    assert result.provenance["grid_coordinates"] == {"latitude": 47.0, "longitude": 8.0}
    assert result.provenance["missing_data"] == {"temperature_2m_mean": [], "precipitation_sum": []}
    assert datetime.fromisoformat(result.provenance["retrieved_at"]).tzinfo is not None
    http.get_json.assert_called_once_with(OpenMeteoHistoricalClient.endpoint, {
        "latitude": 47.0, "longitude": 8.0,
        "start_date": "2014-06-25", "end_date": "2014-06-25",
        "daily": "temperature_2m_mean,precipitation_sum", "models": "era5",
        "timezone": "UTC", "temperature_unit": "celsius", "precipitation_unit": "mm",
        "cell_selection": "nearest", "elevation": "nan", "timeformat": "iso8601",
    })


def test_archive_window_keeps_missing_days_and_nulls_without_partial_totals():
    http = Mock()
    payload = _archive_payload()
    payload["daily"] = {
        "time": ["2014-06-24", "2014-06-25"],
        "temperature_2m_mean": [10.0, None], "precipitation_sum": [0.0, 4.0],
    }
    http.get_json.return_value = payload
    result = HistoricalWeatherProvider(OpenMeteoHistoricalClient(http)).collect(_historical_request(1))

    assert result.status == ContextProviderStatus.PARTIAL
    assert result.data["requested_window"] == {"start": "2014-06-24", "end": "2014-06-26"}
    assert result.data["temperature"]["mean_c"] is None
    assert result.data["precipitation"]["total_mm"] is None
    assert result.data["precipitation"]["daily"] == [
        {"date": "2014-06-24", "total_mm": 0.0},
        {"date": "2014-06-25", "total_mm": 4.0},
        {"date": "2014-06-26", "total_mm": None},
    ]
    assert result.provenance["missing_data"] == {
        "temperature_2m_mean": ["2014-06-25", "2014-06-26"],
        "precipitation_sum": ["2014-06-26"],
    }


def test_archive_complete_window_aggregates_only_requested_dates():
    http = Mock()
    payload = _archive_payload()
    payload["daily"] = {
        "time": ["2014-06-24", "2014-06-25", "2014-06-26"],
        "temperature_2m_mean": [10.0, 12.0, 14.0], "precipitation_sum": [0.0, 4.0, 2.0],
    }
    http.get_json.return_value = payload
    result = HistoricalWeatherProvider(OpenMeteoHistoricalClient(http)).collect(_historical_request(1))

    assert result.status == ContextProviderStatus.SUCCESS
    assert result.data["temperature"]["mean_c"] == 12.0
    assert result.data["precipitation"]["total_mm"] == 6.0


@pytest.mark.parametrize("daily", [
    {}, {"time": ["2014-06-25"], "temperature_2m_mean": [None], "precipitation_sum": [None]},
])
def test_archive_no_values_is_unavailable(daily):
    http = Mock()
    payload = _archive_payload()
    payload["daily"] = daily
    http.get_json.return_value = payload
    result = HistoricalWeatherProvider(OpenMeteoHistoricalClient(http)).collect(_historical_request())

    assert result.status == ContextProviderStatus.UNAVAILABLE
    assert result.data["temperature"]["mean_c"] is None
    assert result.data["precipitation"]["total_mm"] is None
    assert result.provenance["missing_data"]["precipitation_sum"] == ["2014-06-25"]
    assert result.error


@pytest.mark.parametrize("change", [
    {"daily": {"time": ["2024-06-25"], "temperature_2m_mean": [12.0], "precipitation_sum": [4.0]}},
    {"daily": {"time": ["2014-06-25", "2014-06-25"]}},
    {"daily": {"time": ["2014-06-25"], "temperature_2m_mean": []}},
    {"daily": {"time": ["2014-06-25"], "temperature_2m_mean": [float("nan")]}},
    {"daily": {"time": ["2014-06-25"], "precipitation_sum": [-1.0]}},
    {"daily_units": {"temperature_2m_mean": "°F", "precipitation_sum": "mm"}},
    {"utc_offset_seconds": 7200},
    {"error": True, "reason": "No historical data"},
])
def test_archive_rejects_invalid_or_nonhistorical_responses(change):
    http = Mock()
    http.get_json.return_value = {**_archive_payload(), **change}
    result = HistoricalWeatherProvider(OpenMeteoHistoricalClient(http)).collect(_historical_request())

    assert result.status == ContextProviderStatus.UNAVAILABLE
    assert result.data["temperature"] is None
    assert result.data["precipitation"] is None
    assert result.error
    assert http.get_json.call_count == 1  # No substitution or fallback.


@pytest.mark.parametrize("failure", [TimeoutError("archive timeout"), OSError("archive offline")])
def test_archive_transport_failure_stays_unavailable_with_provenance(failure):
    http = Mock()
    http.get_json.side_effect = failure
    result = HistoricalWeatherProvider(OpenMeteoHistoricalClient(http)).collect(_historical_request())

    assert result.status == ContextProviderStatus.UNAVAILABLE
    assert result.provenance["request_params"]["start_date"] == "2014-06-25"
    assert result.provenance["missing_data"]["temperature_2m_mean"] == ["2014-06-25"]
    assert result.data["temperature"] is None
    assert str(failure) in result.error


def test_configured_context_route_stores_historical_weather_as_uninterpreted(db_session, monkeypatch):
    case = _case(db_session)
    case.observation_date = date(2014, 6, 25)
    db_session.commit()
    http = Mock()
    http.get_json.side_effect = lambda url, params: (
        _archive_payload() if url == OpenMeteoHistoricalClient.endpoint
        else {"results": [], "count": 0, "endOfRecords": True}
    )
    monkeypatch.setattr(context_routes, "UrllibJsonClient", lambda: http)
    service = context_routes.get_context_service(db_session)

    outcomes = context_routes.collect_context(case.id, ContextCollectRequest(), db_session, service)
    by_name = {item.provider: item for item in outcomes}
    assert by_name["GHSL-derived urbanization"].status == ContextProviderStatus.UNAVAILABLE
    weather = by_name["historical weather"]
    assert weather.status == ContextProviderStatus.SUCCESS
    assert weather.compatibility == EvidenceCompatibility.UNKNOWN
    assert weather.strength == EvidenceStrength.UNASSESSED
    stored = context_routes.get_context(case.id, db_session, service)
    saved_weather = next(item for item in stored if item.provider == "historical weather")
    assert saved_weather.data["requested_date"] == "2014-06-25"
    assert saved_weather.data["temperature"]["mean_c"] == 12.0
    assert saved_weather.provenance == weather.provenance
    assert saved_weather.compatibility == EvidenceCompatibility.UNKNOWN
    assert saved_weather.strength == EvidenceStrength.UNASSESSED
