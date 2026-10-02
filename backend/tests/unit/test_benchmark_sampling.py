"""The benchmark cannot invent benefits when measurements are missing."""
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import benchmark_sampling  # noqa: E402
from benchmark_sampling import benchmark_execution, summarize  # noqa: E402


def test_empty_benchmark_has_no_claims():
    result = summarize([])
    assert result["status"] == "NO_MEASUREMENTS"
    assert result["workflows"] == {}


def test_only_researcher_supplied_costs_are_summed():
    fixture = {
        "investigation_id": "synthetic-test-only", "workflow": "reference",
        "measurement_source": "test fixture", "source_zone_seconds": "20",
        "plan_seconds": "10", "candidates_examined": "4", "samples_collected": "2",
        "field_cost": "12", "travel_cost": "3", "laboratory_cost": "8",
        "analytical_cost": "7",
    }
    result = summarize([fixture])
    assert result["workflows"]["reference"]["median"]["total_cost"] == 30
    assert "savings" not in result


def test_execution_benchmark_reports_repeated_synthetic_measurements():
    result = benchmark_execution(
        repeated_runs=3,
        warmup_runs=1,
        hypothesis_count=3,
        candidate_reach_count=8,
        candidate_site_count=4,
    )
    assert result["status"] == "SYNTHETIC_EXECUTION_BENCHMARK"
    assert result["timer"] == "time.perf_counter"
    assert result["repeated_runs"] == 3
    assert result["warmup_runs"] == 1
    assert result["input"] == {
        "hypothesis_count": 3,
        "candidate_reach_count": 8,
        "candidate_site_count": 4,
        "decision_reachability_checks_per_run": 12,
    }
    assert set(result["median_execution_seconds"]) == {
        "candidate_generation",
        "sampling_decision",
    }
    assert all(
        elapsed >= 0 for elapsed in result["median_execution_seconds"].values()
    )
    assert result["environment"]["python_version"]
    assert result["environment"]["platform"]
    assert all(
        "field" not in key and "cost" not in key and "accuracy" not in key
        for key in result["median_execution_seconds"]
    )


def test_execution_benchmark_rejects_invalid_run_counts():
    for repeated_runs, warmup_runs in [(0, 0), (1, -1)]:
        try:
            benchmark_execution(repeated_runs=repeated_runs, warmup_runs=warmup_runs)
        except ValueError:
            pass
        else:
            raise AssertionError("invalid benchmark run counts must be rejected")


def test_execution_timer_reports_median_perf_counter_elapsed(monkeypatch):
    ticks = iter([1.0, 1.3, 2.0, 2.1, 3.0, 3.2])
    calls = []
    monkeypatch.setattr(benchmark_sampling, "perf_counter", lambda: next(ticks))

    measured = benchmark_sampling._median_execution_seconds(
        lambda: calls.append(True), repeated_runs=3, warmup_runs=0
    )

    assert measured == pytest.approx(0.2)
    assert len(calls) == 3


def test_measured_workflow_command_remains_available(monkeypatch, tmp_path):
    measurements = tmp_path / "measurements.csv"
    output = tmp_path / "summary.json"
    measurements.write_text(
        ",".join(benchmark_sampling.REQUIRED)
        + "\n"
        + "synthetic,reference,test,20,10,4,2,12,3,8,7\n"
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["benchmark_sampling.py", str(measurements), "--output", str(output)],
    )

    benchmark_sampling.main()

    assert '"status": "MEASURED_WORKFLOWS"' in output.read_text()
