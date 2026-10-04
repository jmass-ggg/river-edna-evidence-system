#!/usr/bin/env python3
"""Summarize researcher-supplied, measured workflow comparisons only."""
from __future__ import annotations

import argparse
import csv
import json
import platform
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

NUMERIC = (
    "source_zone_seconds", "plan_seconds", "candidates_examined",
    "samples_collected", "field_cost", "travel_cost", "laboratory_cost",
    "analytical_cost",
)
REQUIRED = ("investigation_id", "workflow", "measurement_source", *NUMERIC)
EXECUTION_OUTPUT = Path(
    "scientific_validation_outputs/sampling_execution_benchmark.json"
)


def summarize(rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {"status": "NO_MEASUREMENTS", "workflows": {}, "limitations": ["No measured workflow rows were supplied; no benefit or savings are estimated."]}
    by_workflow: dict[str, list[dict[str, float]]] = defaultdict(list)
    for row in rows:
        missing = [key for key in REQUIRED if not row.get(key)]
        if missing:
            raise ValueError(f"Missing measured fields: {', '.join(missing)}")
        measurements = {key: float(row[key]) for key in NUMERIC}
        if any(value < 0 for value in measurements.values()):
            raise ValueError("Measured duration, count, and cost fields must be nonnegative")
        measurements["total_cost"] = sum(measurements[key] for key in ("field_cost", "travel_cost", "laboratory_cost", "analytical_cost"))
        by_workflow[row["workflow"]].append(measurements)
    return {
        "status": "MEASURED_WORKFLOWS",
        "workflows": {
            workflow: {
                "record_count": len(items),
                "median": {key: median(item[key] for item in items) for key in (*NUMERIC, "total_cost")},
            }
            for workflow, items in sorted(by_workflow.items())
        },
        "limitations": [
            "Reported values come from researcher-supplied rows; this summary does not certify their provenance or experimental comparability.",
            "No percent savings, source accuracy, or causal improvement is computed without matched objectives and independently established truth.",
        ],
    }


class SyntheticBenchmarkHydrology:
    """Deterministic graph fixture used only for software execution timing."""

    def __init__(self, candidate_reaches: list[int]):
        self.candidate_reaches = candidate_reaches

    def get_upstream_reaches(self, site_hyriv_id: int) -> list[int]:
        return [*self.candidate_reaches, site_hyriv_id]

    def get_reach(self, hyriv_id: int) -> object:
        if hyriv_id not in self.candidate_reaches:
            raise ValueError("reach is outside the synthetic graph")
        return hyriv_id

    def can_contribute(self, root_hyriv_id: int, site_hyriv_id: int) -> bool:
        return (root_hyriv_id * 31 + site_hyriv_id * 17) % 11 < 5

    def network_distance_km(
        self,
        from_hyriv_id: int,
        to_hyriv_id: int,
        from_fraction: float = 0.5,
        to_fraction: float = 1.0,
    ) -> float:
        return abs(to_hyriv_id - from_hyriv_id) / 10.0


def _synthetic_inputs(
    hypothesis_count: int,
    candidate_reach_count: int,
    candidate_site_count: int,
) -> tuple[object, list[object], list[object], SyntheticBenchmarkHydrology]:
    from app.domain.enums import CaseStatus, SiteType, ValidationStatus
    from app.domain.models import Case, CandidateZone, SamplingSite

    case_id = UUID(int=1)
    case = Case(
        id=case_id,
        target_taxon="Synthetic benchmark taxon",
        observation_date=date(2026, 1, 1),
        detection_site_id=UUID(int=2),
        status=CaseStatus.ACTIVE,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    zones = [
        CandidateZone(
            id=UUID(int=100 + index),
            case_id=case_id,
            label=f"Synthetic H{index + 1}",
            root_hyriv_id=index + 1,
            reach_ids=[index + 1],
            validation_status=ValidationStatus.VERIFIED,
        )
        for index in range(hypothesis_count)
    ]
    candidate_reaches = list(range(1_000, 1_000 + candidate_reach_count))
    sites = [
        SamplingSite(
            id=UUID(int=1_000 + index),
            case_id=case_id,
            label=f"Synthetic site {index + 1}",
            latitude=47.0,
            longitude=7.0,
            hyriv_id=candidate_reaches[index],
            site_type=SiteType.FOLLOW_UP,
            validation_status=ValidationStatus.VERIFIED,
        )
        for index in range(candidate_site_count)
    ]
    return case, zones, sites, SyntheticBenchmarkHydrology(candidate_reaches)


def _median_execution_seconds(operation, repeated_runs: int, warmup_runs: int) -> float:
    for _ in range(warmup_runs):
        operation()
    elapsed = []
    for _ in range(repeated_runs):
        started = perf_counter()
        operation()
        elapsed.append(perf_counter() - started)
    return median(elapsed)


def benchmark_execution(
    repeated_runs: int = 100,
    warmup_runs: int = 10,
    hypothesis_count: int = 8,
    candidate_reach_count: int = 256,
    candidate_site_count: int = 64,
) -> dict:
    """Measure deterministic synthetic execution, separately from workflow data."""
    from app.scientific.sampling.candidate_generator import CandidateSiteGenerator
    from app.scientific.sampling.engine import ScaffoldSamplingDecisionEngine

    if repeated_runs < 1 or warmup_runs < 0:
        raise ValueError("repeated_runs must be positive and warmup_runs nonnegative")
    if min(hypothesis_count, candidate_reach_count, candidate_site_count) < 1:
        raise ValueError("execution benchmark input sizes must be positive")
    if candidate_site_count > candidate_reach_count:
        raise ValueError("candidate_site_count cannot exceed candidate_reach_count")

    case, zones, sites, hydrology = _synthetic_inputs(
        hypothesis_count, candidate_reach_count, candidate_site_count
    )
    generator = CandidateSiteGenerator(hydrology)
    decision_engine = ScaffoldSamplingDecisionEngine()

    def generate_candidates() -> None:
        generator.generate(zones, 10_000, candidate_hyriv_ids=candidate_reaches)

    candidate_reaches = hydrology.candidate_reaches

    def make_decision() -> None:
        evaluations = decision_engine.evaluate_candidates(
            case, zones, sites, hydrology
        )
        decision_engine.make_recommendation(evaluations)

    return {
        "status": "SYNTHETIC_EXECUTION_BENCHMARK",
        "timer": "time.perf_counter",
        "repeated_runs": repeated_runs,
        "warmup_runs": warmup_runs,
        "input": {
            "hypothesis_count": hypothesis_count,
            "candidate_reach_count": candidate_reach_count,
            "candidate_site_count": candidate_site_count,
            "decision_reachability_checks_per_run": (
                hypothesis_count * candidate_site_count
            ),
        },
        "median_execution_seconds": {
            "candidate_generation": _median_execution_seconds(
                generate_candidates, repeated_runs, warmup_runs
            ),
            "sampling_decision": _median_execution_seconds(
                make_decision, repeated_runs, warmup_runs
            ),
        },
        "environment": {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "processor": platform.processor() or "unreported",
        },
        "limitations": [
            "Synthetic deterministic graph inputs measure software execution only.",
            "Times depend on the recorded runtime environment and are not field, laboratory, cost, savings, or biological-accuracy measurements.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "measurements", type=Path, nargs="?", help="CSV of observed workflow runs"
    )
    parser.add_argument(
        "--execution",
        action="store_true",
        help="run the separate synthetic software-execution benchmark",
    )
    parser.add_argument("--repeats", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.execution:
        if args.measurements is not None:
            parser.error("measurements cannot be supplied with --execution")
        result = benchmark_execution(args.repeats, args.warmups)
        output = args.output or EXECUTION_OUTPUT
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(output)
        return
    if args.measurements is None:
        parser.error("measurements is required unless --execution is used")
    output = args.output or Path(
        "scientific_validation_outputs/benchmark_summary.json"
    )
    with args.measurements.open(newline="") as stream:
        reader = csv.DictReader(stream)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise SystemExit("Measurement CSV lacks required columns")
        result = summarize(list(reader))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(output)


if __name__ == "__main__":
    main()
