"""Deterministic topology-only candidate-site generation."""

from collections import defaultdict
from typing import Iterable

from app.domain.enums import ValidationStatus
from app.domain.models import (
    CandidateEquivalenceClass,
    CandidateGenerationResult,
    CandidateZone,
    GeneratedCandidateSite,
)
from app.scientific.interfaces import HydrologyEngine


class CandidateSiteGenerator:
    """Group upstream reaches by hypothesis signature and select representatives."""

    def __init__(
        self,
        hydrology_engine: HydrologyEngine,
        reach_coordinates: dict[int, tuple[float, float]] | None = None,
    ):
        self.hydrology_engine = hydrology_engine
        self.reach_coordinates = reach_coordinates or {}

    def generate(
        self,
        zones: list[CandidateZone],
        site_a_hyriv_id: int,
        site_a_fraction: float = 1.0,
        candidate_hyriv_ids: Iterable[int] | None = None,
    ) -> CandidateGenerationResult:
        """Generate one nearest-to-A representative per useful signature."""
        ordered_zones = sorted(zones, key=lambda zone: (zone.label, zone.root_hyriv_id))
        labels = [zone.label for zone in ordered_zones]
        if not ordered_zones:
            return CandidateGenerationResult(
                site_a_hyriv_id=site_a_hyriv_id,
                hypothesis_labels=[],
                eligible_reach_count=0,
                equivalence_classes=[],
                candidates=[],
                limitation=(
                    "No remaining hypotheses were supplied; topology-based "
                    "hypothesis discrimination was not evaluated."
                ),
            )

        validated_upstream = set(
            self.hydrology_engine.get_upstream_reaches(site_a_hyriv_id)
        )
        requested = (
            validated_upstream
            if candidate_hyriv_ids is None
            else set(candidate_hyriv_ids)
        )
        eligible = sorted((requested & validated_upstream) - {site_a_hyriv_id})

        grouped: dict[tuple[int, ...], list[tuple[int, float]]] = defaultdict(list)
        for hyriv_id in eligible:
            try:
                self.hydrology_engine.get_reach(hyriv_id)
                signature = tuple(
                    int(
                        self.hydrology_engine.can_contribute(
                            zone.root_hyriv_id, hyriv_id
                        )
                    )
                    for zone in ordered_zones
                )
                distance = self.hydrology_engine.network_distance_km(
                    hyriv_id,
                    site_a_hyriv_id,
                    from_fraction=0.5,
                    to_fraction=site_a_fraction,
                )
            except (KeyError, ValueError):
                continue
            if distance is None:
                continue
            grouped[signature].append((hyriv_id, distance))

        classes: list[CandidateEquivalenceClass] = []
        candidates: list[GeneratedCandidateSite] = []
        hypothesis_count = len(ordered_zones)
        for signature in sorted(grouped):
            members = sorted(grouped[signature], key=lambda item: (item[1], item[0]))
            reachable_count = sum(signature)
            score = reachable_count * (hypothesis_count - reachable_count)
            class_name = "signature:" + "".join(str(value) for value in signature)
            representative = members[0] if score > 0 else None
            classes.append(
                CandidateEquivalenceClass(
                    equivalence_class=class_name,
                    signature=list(signature),
                    pair_separation_score=score,
                    hyriv_ids=sorted(hyriv_id for hyriv_id, _ in members),
                    representative_hyriv_id=(
                        representative[0] if representative else None
                    ),
                )
            )
            if representative is None:
                continue
            hyriv_id, distance = representative
            coordinate = self.reach_coordinates.get(hyriv_id)
            candidates.append(
                GeneratedCandidateSite(
                    hyriv_id=hyriv_id,
                    latitude=coordinate[0] if coordinate else None,
                    longitude=coordinate[1] if coordinate else None,
                    network_distance_km=distance,
                    signature=list(signature),
                    pair_separation_score=score,
                    equivalence_class=class_name,
                    equivalent_hyriv_ids=sorted(
                        member_id for member_id, _ in members
                    ),
                    selection_reason=(
                        ("Nearest network distance to Site A within this topology " if site_a_hyriv_id == 20446064 else f"Nearest network distance to detection reach {site_a_hyriv_id} within this topology ")
                        + "equivalence class. Representative selection does not "
                        "imply greater ecological value."
                    ),
                    validation_status=ValidationStatus.VERIFIED,
                )
            )

        candidates.sort(
            key=lambda candidate: (
                -candidate.pair_separation_score,
                candidate.equivalence_class,
                candidate.network_distance_km,
                candidate.hyriv_id,
            )
        )
        return CandidateGenerationResult(
            site_a_hyriv_id=site_a_hyriv_id,
            hypothesis_labels=labels,
            eligible_reach_count=sum(len(members) for members in grouped.values()),
            equivalence_classes=classes,
            candidates=candidates,
            limitation=(
                "Candidate optimization uses topology-based hypothesis "
                "discrimination only; field accessibility, safety, land ownership, "
                "cost, transport, and decay are not evaluated."
            ),
        )
