"""Historical weather context, including explicit ERA5 archive extraction."""
from datetime import date, datetime, timedelta, timezone
import math
from typing import Any

from app.context.interfaces import ContextRequest, JsonHttpClient, ProviderResult, SpatialContextClient
from app.domain.enums import ContextProviderStatus


class OpenMeteoHistoricalClient:
    """Daily ERA5 reanalysis; no best-match model or forecast fallback.

    Source and parameter definitions: https://open-meteo.com/en/docs/historical-weather-api
    """

    endpoint = "https://archive-api.open-meteo.com/v1/archive"

    def __init__(self, http_client: JsonHttpClient):
        self.http_client = http_client

    def query(self, *, latitude: float, longitude: float, start_date: str, end_date: str) -> dict[str, Any]:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        params = {
            "latitude": latitude, "longitude": longitude,
            "start_date": start_date, "end_date": end_date,
            "daily": "temperature_2m_mean,precipitation_sum", "models": "era5",
            "timezone": "UTC", "temperature_unit": "celsius", "precipitation_unit": "mm",
            "cell_selection": "nearest", "elevation": "nan", "timeformat": "iso8601",
        }
        dates = [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]
        variables = {"temperature_2m_mean": "°C", "precipitation_sum": "mm"}
        provenance = {
            "endpoint": self.endpoint, "request_params": params,
            "source": "Copernicus Climate Change Service / ECMWF ERA5 via Open-Meteo",
            "documentation": "https://open-meteo.com/en/docs/historical-weather-api",
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "spatial_resolution": "0.25 degrees (approximately 25 km)",
            "temporal_resolution": "daily aggregation of hourly reanalysis",
            "timezone": "UTC", "elevation_downscaling": False,
            "missing_data": {variable: list(dates) for variable in variables},
        }
        raw = {
            "source_model": "ERA5", "temperature": None, "precipitation": None,
            "provenance": provenance,
            "limitations": [
                "ERA5 values are gridded reanalysis estimates, not measurements at the sampling site.",
                "Daily values cover UTC calendar days; the observation's local timezone is not supplied.",
                "The nearest grid cell is used without elevation downscaling or spatial buffer averaging.",
            ],
        }
        try:
            if start > end or start < date(1940, 1, 1) or end > datetime.now(timezone.utc).date():
                raise ValueError("Requested window is outside the historical ERA5 date range")
            if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
                raise ValueError("Invalid weather coordinates")
            payload = self.http_client.get_json(self.endpoint, params)
            if not isinstance(payload, dict) or payload.get("error"):
                raise ValueError("Archive returned an error or invalid response")
            provenance["grid_coordinates"] = {
                "latitude": payload.get("latitude"), "longitude": payload.get("longitude"),
            }
            provenance["grid_elevation_m"] = payload.get("elevation")
            provenance["response_timezone"] = payload.get("timezone")
            provenance["utc_offset_seconds"] = payload.get("utc_offset_seconds")
            if payload.get("utc_offset_seconds") != 0:
                raise ValueError("Archive did not confirm the requested UTC day boundaries")
            daily, units = payload.get("daily") or {}, payload.get("daily_units") or {}
            if not isinstance(daily, dict) or not isinstance(units, dict):
                raise ValueError("Invalid archive daily data or units")
            provenance["daily_units"] = units
            times = daily.get("time", [])
            if (not isinstance(times, list) or any(not isinstance(day, str) for day in times)
                    or len(set(times)) != len(times) or not set(times).issubset(dates)):
                raise ValueError("Archive dates do not match the requested historical window")
            values = {}
            for variable, unit in variables.items():
                series = daily.get(variable)
                if series is None:
                    series = [None] * len(times)
                if not isinstance(series, list) or len(series) != len(times):
                    raise ValueError(f"Archive dates and {variable} values are misaligned")
                if any(value is not None for value in series) and units.get(variable) != unit:
                    raise ValueError(f"Unexpected or missing units for {variable}")
                for value in series:
                    if value is not None and (
                        type(value) not in (int, float) or not math.isfinite(value)
                        or (variable == "precipitation_sum" and value < 0)
                    ):
                        raise ValueError(f"Invalid numeric value for {variable}")
                by_date = dict(zip(times, series))
                values[variable] = [by_date.get(day) for day in dates]
            provenance["missing_data"] = {
                variable: [day for day, value in zip(dates, series) if value is None]
                for variable, series in values.items()
            }
            temperatures, precipitation = values["temperature_2m_mean"], values["precipitation_sum"]
            raw["temperature"] = {
                "mean_c": sum(temperatures) / len(dates) if all(v is not None for v in temperatures) else None,
                "unit": "°C", "daily": [
                    {"date": day, "mean_c": value} for day, value in zip(dates, temperatures)
                ],
            }
            raw["precipitation"] = {
                "total_mm": sum(precipitation) if all(v is not None for v in precipitation) else None,
                "unit": "mm", "daily": [
                    {"date": day, "total_mm": value} for day, value in zip(dates, precipitation)
                ],
            }
            if not any(value is not None for series in values.values() for value in series):
                raw["unavailable_reason"] = "Archive returned no weather values for the requested window"
            if any(provenance["missing_data"].values()):
                raw["limitations"].append("Missing daily values are retained as null; incomplete window aggregates are not calculated.")
        except (OSError, ValueError) as exc:
            raw["unavailable_reason"] = f"Historical ERA5 data unavailable: {exc}"
        return raw


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
        if any(data["provenance"].get("missing_data", {}).values()):
            status = ContextProviderStatus.PARTIAL
        if raw.get("unavailable_reason"):
            status = ContextProviderStatus.UNAVAILABLE
        return ProviderResult(
            provider=self.name,
            evidence_type="context_historical_weather",
            status=status,
            data=data,
            provenance=data["provenance"],
            error=raw.get("unavailable_reason"),
            limitations=[
                "Temperature is environmental context and does not diagnose or predict disease.",
                "Precipitation is meteorological context and does not prove eDNA transport.",
                *list(raw.get("limitations", [])),
            ],
        )
