"""Generic adapter for GHSL-derived built-up context."""
from app.context.interfaces import ContextRequest, ProviderResult, SpatialContextClient
from app.domain.enums import ContextProviderStatus


class UrbanizationProvider:
    name = "GHSL-derived urbanization"

    def __init__(self, client: SpatialContextClient):
        self.client = client

    def collect(self, request: ContextRequest) -> ProviderResult:
        buffer_m = request.urban_buffer_m or request.radius_m
        raw = self.client.query(
            latitude=request.latitude, longitude=request.longitude, buffer_m=buffer_m
        )
        data = {
            "provider": self.name,
            "built_up_metric": raw.get("built_up_metric"),
            "source_year": raw.get("source_year"),
            "resolution": raw.get("resolution"),
            "spatial_buffer_m": buffer_m,
            "source_version": raw.get("source_version"),
            "temporal_alignment": raw.get("temporal_alignment"),
            "provenance": raw.get("provenance", {}),
        }
        required = ("built_up_metric", "source_year", "resolution", "source_version")
        status = (
            ContextProviderStatus.SUCCESS
            if all(data[key] is not None for key in required)
            else ContextProviderStatus.PARTIAL
        )
        return ProviderResult(
            provider=self.name,
            evidence_type="context_urbanization",
            status=status,
            data=data,
            provenance=data["provenance"],
            limitations=[
                "Built-up metrics provide built-environment context and do not establish pollution, degradation, or health risk.",
                *list(raw.get("limitations", [])),
            ],
        )
