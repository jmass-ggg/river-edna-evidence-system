"""Extension point for scientifically reviewed hypothesis-state resolution."""
from typing import Protocol

from app.domain.enums import HypothesisStatus


class HypothesisStateResolver(Protocol):
    def resolve(self, zone, assessments, summary: dict[str, int]) -> tuple[HypothesisStatus, str]: ...


class UnknownHypothesisStateResolver:
    """Safe Light-phase placeholder; it makes no hypothesis inference."""

    def resolve(self, zone, assessments, summary: dict[str, int]) -> tuple[HypothesisStatus, str]:
        return (
            HypothesisStatus.UNKNOWN,
            "No validated hypothesis-state resolver is configured; status remains UNKNOWN.",
        )


class ConservativeHypothesisStateResolver:
    """Resolve only assessments carrying a validated directional rule ID."""

    version = "hypothesis.validated_direction_only.v1"
    validated_rule_ids = {"hydrorivers.directed_contribution.v1"}

    def resolve(self, zone, assessments, summary: dict[str, int]) -> tuple[HypothesisStatus, str]:
        validated = [item for item in assessments if item.rule_id in self.validated_rule_ids]
        supports = sum(item.compatibility.value == "SUPPORTS" for item in validated)
        contradicts = sum(item.compatibility.value == "CONTRADICTS" for item in validated)
        if supports and contradicts:
            return HypothesisStatus.CONFLICTING, "Validated directional evidence contains both SUPPORTS and CONTRADICTS assessments."
        if supports:
            return HypothesisStatus.SUPPORTED, "At least one validated directional assessment SUPPORTS this hypothesis and none CONTRADICTS it."
        if contradicts:
            return HypothesisStatus.WEAKENED, "Validated directional evidence CONTRADICTS this hypothesis, but no validated elimination rule exists."
        return HypothesisStatus.UNKNOWN, "No validated directional evidence resolves this hypothesis; unsupported evidence cannot alter its state."

    @staticmethod
    def eligible(status: HypothesisStatus) -> bool:
        """V4 defines no elimination criterion, so all resolved states remain eligible."""
        return status != HypothesisStatus.ELIMINATED
