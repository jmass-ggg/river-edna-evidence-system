"""Generic adapter for historical temperature and precipitation context."""
from datetime import datetime, timedelta, timezone

from app.context.interfaces import ContextRequest, ProviderResult, SpatialContextClient
from app.domain.enums import ContextProviderStatus


class HistoricalWeatherProvider:
    name = "historical weather"

    def __init__(self, client: SpatialContextClient):
        self.client = client

    def collect(self, request: ContextRequest) -> ProviderResult:
        start = request.observation_date - timedelta(days=request.weather_window_days)
        end = request.observation_date + timedelta(days=request.weather_window_days)
        raw = self.client.query(
            latitude=request.latitude,
            longitude=request.longitude,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        retrieved_at = datetime.now(timezone.utc).isoformat()
        data = {
            "provider": self.name,
            "requested_coordinates": {
                "latitude": request.latitude,
                "longitude": request.longitude,
            },
            "requested_date": request.observation_date.isoformat(),
            "requested_window": {"start": start.isoformat(), "end": end.isoformat()},
            "temperature": raw.get("temperature"),
            "precipitation": raw.get("precipitation"),
            "source_model": raw.get("source_model"),
            "retrieved_at": retrieved_at,
            "provenance": raw.get("provenance", {}),
        }
        required = ("temperature", "precipitation", "source_model")
        status = (
            ContextProviderStatus.SUCCESS
            if all(data[key] is not None for key in required)
            else ContextProviderStatus.PARTIAL
        )
        return ProviderResult(
            provider=self.name,
            evidence_type="context_historical_weather",
            status=status,
            data=data,
            provenance=data["provenance"],
            limitations=[
                "Temperature is environmental context and does not diagnose or predict disease.",
                "Precipitation is meteorological context and does not prove eDNA transport.",
                *list(raw.get("limitations", [])),
            ],
        )
