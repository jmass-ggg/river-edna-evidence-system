"""GBIF occurrence adapter using the official occurrence search endpoint."""
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import math

from app.context.interfaces import ContextRequest, JsonHttpClient, ProviderResult
from app.domain.enums import ContextProviderStatus


class UrllibJsonClient:
    """Small injectable standard-library JSON client."""

    def get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        with urlopen(f"{url}?{urlencode(params)}", timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))


class GbifOccurrenceProvider:
    name = "GBIF"
    endpoint = "https://api.gbif.org/v1/occurrence/search"

    def __init__(self, http_client: JsonHttpClient, result_limit: int = 100):
        self.http_client = http_client
        self.result_limit = result_limit

    def collect(self, request: ContextRequest) -> ProviderResult:
        retrieved_at = datetime.now(timezone.utc).isoformat()
        lat_delta = request.radius_m / 111_320.0
        lon_delta = request.radius_m / max(1.0, 111_320.0 * math.cos(math.radians(request.latitude)))
        south, north = request.latitude - lat_delta, request.latitude + lat_delta
        west, east = request.longitude - lon_delta, request.longitude + lon_delta
        geometry = (
            f"POLYGON(({west} {south},{east} {south},{east} {north},"
            f"{west} {north},{west} {south}))"
        )
        payload = self.http_client.get_json(
            self.endpoint,
            {
                "scientificName": request.query,
                "geometry": geometry,
                "limit": self.result_limit,
            },
        )
        records = payload.get("results", [])
        compact = []
        for record in records:
            compact.append(
                {
                    "occurrence_id": record.get("key") or record.get("occurrenceID"),
                    "latitude": record.get("decimalLatitude"),
                    "longitude": record.get("decimalLongitude"),
                    "date": record.get("eventDate") or record.get("dateIdentified"),
                    "dataset_id": record.get("datasetKey"),
                }
            )
        status = (
            ContextProviderStatus.PARTIAL
            if payload.get("endOfRecords") is False
            else ContextProviderStatus.SUCCESS
        )
        return ProviderResult(
            provider=self.name,
            evidence_type="context_gbif_occurrence",
            status=status,
            data={
                "provider": self.name,
                "query": request.query,
                "radius_m": request.radius_m,
                "count": int(payload.get("count", len(records))),
                "occurrences": compact,
                "retrieved_at": retrieved_at,
                "provenance": {"endpoint": self.endpoint},
                "limitations": [
                    "GBIF records provide species-occurrence context and do not prove current presence at the case site."
                ],
            },
            provenance={"endpoint": self.endpoint, "retrieved_at": retrieved_at},
            limitations=[
                "GBIF records provide species-occurrence context and do not prove current presence at the case site.",
                "Results may be truncated by the configured compact-result limit.",
            ],
        )
