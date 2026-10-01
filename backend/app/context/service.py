"""Orchestration and persistence for non-scientific context collection."""
from uuid import UUID

from app.context.interfaces import ContextProvider, ContextRequest, ProviderResult
from app.domain.enums import ContextProviderStatus, EvidenceCompatibility, EvidenceStrength
from app.repositories.evidence import EvidenceRepository


CONTEXT_EVIDENCE_TYPES = {
    "context_gbif_occurrence",
    "context_urbanization",
    "context_historical_weather",
}


class ContextCollectionService:
    def __init__(self, evidence_repository: EvidenceRepository, providers: list[ContextProvider]):
        self.evidence_repository = evidence_repository
        self.providers = providers

    def collect(self, case_id: UUID, request: ContextRequest) -> list[dict]:
        outcomes = []
        for provider in self.providers:
            try:
                result = provider.collect(request)
            except NotImplementedError as exc:
                result = ProviderResult(
                    provider=provider.name,
                    evidence_type=f"context_{provider.name.lower().replace(' ', '_')}",
                    status=ContextProviderStatus.UNAVAILABLE,
                    error=str(exc),
                    limitations=["No context value was inferred because the provider is unavailable."],
                )
            except Exception as exc:
                result = ProviderResult(
                    provider=provider.name,
                    evidence_type=f"context_{provider.name.lower().replace(' ', '_')}",
                    status=ContextProviderStatus.ERROR,
                    error=str(exc),
                    limitations=["No context value was inferred because collection failed."],
                )

            evidence_id = None
            if result.status in {ContextProviderStatus.SUCCESS, ContextProviderStatus.PARTIAL}:
                stored_value = dict(result.data or {})
                stored_value["provider_status"] = result.status.value
                stored_value["limitations"] = result.limitations
                evidence = self.evidence_repository.add_evidence(
                    case_id=case_id,
                    evidence_type=result.evidence_type,
                    source=result.provider,
                    value=stored_value,
                    provenance=result.provenance,
                )
                evidence_id = evidence.id
            outcomes.append(self._serialize(result, evidence_id))
        return outcomes

    def get_context(self, case_id: UUID) -> list[dict]:
        return [
            {
                "evidence_id": item.id,
                "provider": item.source,
                "evidence_type": item.evidence_type,
                "status": ContextProviderStatus(
                    item.value.get("provider_status", ContextProviderStatus.SUCCESS.value)
                ),
                "data": item.value,
                "provenance": item.provenance,
                "limitations": item.value.get("limitations", []),
                "error": None,
                "compatibility": EvidenceCompatibility.UNKNOWN,
                "strength": EvidenceStrength.UNASSESSED,
            }
            for item in self.evidence_repository.get_evidence_by_case(case_id)
            if item.evidence_type in CONTEXT_EVIDENCE_TYPES
        ]

    @staticmethod
    def _serialize(result: ProviderResult, evidence_id: UUID | None) -> dict:
        return {
            "evidence_id": evidence_id,
            "provider": result.provider,
            "evidence_type": result.evidence_type,
            "status": result.status,
            "data": result.data,
            "provenance": result.provenance,
            "limitations": result.limitations,
            "error": result.error,
            "compatibility": EvidenceCompatibility.UNKNOWN,
            "strength": EvidenceStrength.UNASSESSED,
        }
