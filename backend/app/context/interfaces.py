"""Provider contracts kept independent from transport implementations."""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.domain.enums import ContextProviderStatus


@dataclass(frozen=True)
class ContextRequest:
    query: str
    latitude: float
    longitude: float
    observation_date: date
    radius_m: int
    weather_window_days: int = 0
    urban_buffer_m: int | None = None


@dataclass
class ProviderResult:
    provider: str
    evidence_type: str
    status: ContextProviderStatus
    data: dict[str, Any] | None = None
    provenance: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    error: str | None = None


class ContextProvider(Protocol):
    name: str

    def collect(self, request: ContextRequest) -> ProviderResult: ...


class JsonHttpClient(Protocol):
    def get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]: ...


class SpatialContextClient(Protocol):
    def query(self, **kwargs: Any) -> dict[str, Any]: ...


class UnavailableSpatialClient:
    """Explicit placeholder until a configured dataset adapter is supplied."""

    def __init__(self, source: str):
        self.source = source

    def query(self, **kwargs: Any) -> dict[str, Any]:
        raise NotImplementedError(f"{self.source} data source is not configured")
