#!/usr/bin/env python3
"""Reproduce the frozen Wigger investigation through the public API."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.scientific_results import canonical_scientific_result, reference_identities
EXPECTED_HASHES = {
    "data_preflight/outputs/upstream_reaches_real.csv": "f767d1068d7ee911a1a3cab07ff27db417858d611ae6951a629312be81ce449b",
    "data_preflight/outputs/upstream_edges.csv": "1811d989f680273729c2d4d24a3ad990e7a81ba7424c5336079b8f2004fcf312",
    "data_preflight/outputs/candidate_zones_real.geojson": "b19b025efdb5e918f340796a51f0f04d6b3adf2cbf3cc8af5e425e8289bd0368",
    "data_preflight/outputs/candidate_sampling_sites.csv": "8f296900d430587f01656ba9d3f82fa0ba54225d3434e74cade6ec9128f2ae59",
    "data_preflight/raw/carraro/eDNA_data.mat": "9938c931402a902d686e26acca93fbc3a2cf78e061919ffebe416d7a61a536c2",
    "data_preflight/raw/carraro/RUN_MODEL.m": "c05f3cd49e0519029314357cb27d6c6265dd1067ff77633e2418f3b2e53b41eb",
}


def verify_inputs():
    result = {}
    for relative, expected in EXPECTED_HASHES.items():
        path = ROOT / relative
        if not path.is_file():
            raise SystemExit(f"Missing required source: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"Checksum mismatch: {relative}\nexpected {expected}\nactual   {actual}")
        result[relative] = actual
    return result


class HttpApi:
    def __init__(self, base_url): self.base_url = base_url.rstrip("/")
    def call(self, method, path, payload=None):
        body = None if payload is None else json.dumps(payload).encode()
        request = Request(self.base_url + path, data=body, method=method, headers={"Content-Type": "application/json"})
        try:
            with urlopen(request, timeout=60) as response:
                return json.loads(response.read())
        except HTTPError as error:
            raise RuntimeError(f"{method} {path}: HTTP {error.code}: {error.read().decode()}") from error


def execute(api, checksums, audit=None):
    api.call("GET", "/health")
    first = api.call("GET", "/demo/wigger")
    second = api.call("GET", "/demo/wigger")
    if first["case_id"] != second["case_id"]:
        raise RuntimeError("Demo loader is not idempotent")
    case_id = first["case_id"]
    case = api.call("GET", f"/cases/{case_id}")
    evidence = api.call("GET", f"/cases/{case_id}/evidence")
    assessments = api.call("GET", f"/cases/{case_id}/evidence-assessment")
    sites = api.call("GET", f"/cases/{case_id}/sites")
    zones = api.call("GET", f"/cases/{case_id}/zones")
    map_data = api.call("GET", "/demo/wigger/map")
    upstream = api.call("GET", "/hydrology/upstream/20446064")
    generated = api.call("GET", f"/cases/{case_id}/generated-candidates")
    decision = api.call("POST", f"/cases/{case_id}/sampling-decision", {})
    trace = api.call("GET", f"/cases/{case_id}/decision-trace")
    reinvestigation = api.call("POST", f"/cases/{case_id}/reinvestigate", {})
    context = api.call("GET", f"/cases/{case_id}/context")
    one_health = api.call("GET", f"/cases/{case_id}/one-health")
    if audit is not None:
        audit.update({"case": case, "demo_load": first, "repeated_demo_load": second,
            "evidence": evidence, "assessments": assessments, "sites": sites, "zones": zones,
            "map": map_data, "upstream": upstream, "generated_candidates": generated,
            "decision": decision, "trace": trace, "reinvestigation": reinvestigation,
            "context": context, "one_health": one_health})
    identities = reference_identities(sites, zones, evidence)
    for candidate in reinvestigation["candidate_generation"].get("candidates", []):
        identities[candidate["site_id"]] = f"reach:{candidate['hyriv_id']}:GENERATED_REPRESENTATIVE"

    site_by_id = {site["id"]: site["label"] for site in sites}
    reach_features = map_data["river_network"]["features"]
    zone_lengths = {}
    for feature in map_data["source_zones"]["features"]:
        label = feature["properties"]["zone"]
        zone_lengths[label] = zone_lengths.get(label, 0.0) + float(feature["properties"]["LENGTH_KM"])
    normalized = {
        "schema_version": "wigger-reproduction.v2",
        "inputs": {"checksums": checksums, "crs": map_data["crs"], "provenance": map_data["provenance"]},
        "observation": first["summary"]["historical_observation"],
        "case": {"target_taxon": case["target_taxon"], "observation_date": case["observation_date"], "status": case["status"]},
        "hydrology": {
            "site_a_hyriv_id": 20446064,
            "reach_count_including_site_a": upstream["count"] + 1,
            "upstream_reach_count": upstream["count"],
            "network_length_km": round(sum(float(f["properties"]["LENGTH_KM"]) for f in reach_features), 6),
        },
        "sites": [{k: site[k] for k in ("label","latitude","longitude","network_latitude","network_longitude","hyriv_id","snap_distance_m","validation_status","role","metadata")} for site in sites],
        "zones": [{"label": zone["label"], "root_hyriv_id": zone["root_hyriv_id"], "reach_ids": zone["reach_ids"], "reach_count": len(zone["reach_ids"]), "total_length_km": round(zone_lengths[zone["label"]], 6), "validation_status": zone["validation_status"]} for zone in zones],
        "evidence": [{"evidence_type": item["evidence_type"], "source": item["source"], "value": item["value"], "quality": item["quality"], "provenance": item["provenance"]} for item in evidence],
        "assessments": [
            {
                "zone_label": item["zone_label"],
                "summary": item["summary"],
                "assessments": [
                    {
                        key: assessment[key]
                        for key in (
                            "compatibility", "rule_id", "reason", "strength",
                            "strength_reason", "strength_limitations",
                        )
                    }
                    for assessment in item["assessments"]
                ],
            }
            for item in assessments
        ],
        "generated_candidates": [{k: item[k] for k in ("hyriv_id","latitude","longitude","network_distance_km","signature","distinguished_hypothesis_pairs","pair_separation_score","equivalence_class","selection_reason","validation_status")} for item in generated["candidates"]],
        "generated_candidate_decision": {"status": generated["decision_status"], "reason": generated["decision_reason"], "limitation": generated["limitation"]},
        "registered_site_decision": {"status": decision["status"], "recommended_sites": [site_by_id.get(value, value) for value in decision["recommended_site_ids"]], "rationale": decision["rationale"]},
        "decision_trace": {k: trace[k] for k in ("evidence_used","rules_applied","hydrology_checks","assumptions","limitations")},
        "reinvestigation": {
            "status": reinvestigation["status"],
            "hypotheses": [
                {
                    key: hypothesis[key]
                    for key in (
                        "zone_label", "status", "reason", "supports",
                        "contradicts", "neutral", "unknown",
                    )
                }
                for hypothesis in reinvestigation["hypotheses"]
            ],
            "candidate_generation": reinvestigation["candidate_generation"],
            "scientific_result": reinvestigation.get("scientific_result", {}),
            "sampling_decision": {
                "status": reinvestigation["sampling_decision"]["status"],
                "rationale": reinvestigation["sampling_decision"]["rationale"],
            },
        },
        "environmental_context": context,
        "one_health": {"framework": one_health["framework"], "pathways": one_health["pathways"], "scientific_logic_implemented": one_health["scientific_logic_implemented"]},
    }
    return canonical_scientific_result(_relative_paths(normalized), identities)


def _relative_paths(value):
    """Remove checkout-specific path prefixes from comparable scientific output."""
    if isinstance(value, dict):
        return {key: _relative_paths(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_relative_paths(item) for item in value]
    if isinstance(value, str) and value.startswith(str(ROOT) + os.sep):
        return str(Path(value).relative_to(ROOT))
    return value


def report(result):
    observation = result["observation"]
    decision = result["registered_site_decision"]
    lines = [
        "# Reproduced Wigger River Investigation", "",
        "## Investigation summary", "",
        f"The frozen Wigger case evaluates the historical {observation['species']} eDNA observation at {observation['station']} and compares upstream source-zone hypotheses. The registered-site sampling decision is **{decision['status']}**.", "",
        "## Original eDNA detection", "",
        f"- Station: {observation['station']} (Site A)", f"- Species: {observation['species']} ({observation['species_code']})", f"- Observation index: {observation['observation_index']}", f"- Date: {observation['date']}", f"- Concentration: {observation['concentration_mol_l']} mol/L", f"- State: {observation['state']}", "- Replicate results and laboratory assay metadata: unavailable in the verified H001 record.", "",
        "## Hydrological investigation", "",
        f"- Site A HydroRIVERS reach: {result['hydrology']['site_a_hyriv_id']}", f"- Reaches including Site A: {result['hydrology']['reach_count_including_site_a']}", f"- Loaded network length: {result['hydrology']['network_length_km']} km", "",
        "## Source hypotheses", "",
        "| Zone | Root reach | Reaches | Length km | Validation |", "| --- | ---: | ---: | ---: | --- |",
    ]
    lines += [f"| {z['label']} | {z['root_hyriv_id']} | {z['reach_count']} | {z['total_length_km']} | {z['validation_status']} |" for z in result["zones"]]
    lines += ["", "Hydrological connection establishes a possible mapped transport pathway. It does not confirm the biological source.", "", "## Evidence assessment", "", "| Zone | Supports | Contradicts | Neutral | Unknown |", "| --- | ---: | ---: | ---: | ---: |"]
    lines += [f"| {a['zone_label']} | {a['summary']['supports']} | {a['summary']['contradicts']} | {a['summary']['neutral']} | {a['summary']['unknown']} |" for a in result["assessments"]]
    lines += ["", "The historical eDNA measurement remains UNKNOWN because no validated compatibility rule applies to that evidence type. Directed connectivity is assessed with `hydrorivers.directed_contribution.v1`.", "", "## Candidate comparison", "", "| Reach | Signature | Distinguished pairs | Pair-separation score | Network distance km | Validation |", "| ---: | --- | --- | ---: | ---: | --- |"]
    lines += [f"| {c['hyriv_id']} | {c['signature']} | {', '.join(' vs '.join(pair) for pair in c['distinguished_hypothesis_pairs'])} | {c['pair_separation_score']} | {c['network_distance_km']:.6f} | {c['validation_status']} |" for c in result["generated_candidates"]]
    lines += ["", "Generated candidates are nearest-to-A representatives of upstream reachability-signature classes with positive pair separation. They are counterfactual reaches, not automatically registered field sites. The persisted decision evaluates the separately registered Sites B, C, and D; Site D is a shared-trunk comparator rather than the nearest generated representative of its signature. An incomplete validated network yields INSUFFICIENT_DATA, while no useful discriminator yields ABSTAIN. Field access, assay quality, transport, and cost are unassessed.", "", "## Sampling decision", "", f"**{decision['status']}** — {decision['rationale']}", "", f"Eligible registered sites: {', '.join(decision['recommended_sites']) or 'none'}.", "", "## Decision audit trail", "", f"- Rules: {', '.join(result['decision_trace']['rules_applied']) or 'none'}", "- Assumptions:"]
    lines += [f"  - {value}" for value in result["decision_trace"]["assumptions"]]
    lines += ["- Limitations:"] + [f"  - {value}" for value in result["decision_trace"]["limitations"]]
    lines += ["", "## Follow-up sampling", "", "Sites tied or recommended by the topology criterion remain eligible for a field investigation. A follow-up record should preserve its site/reach, time, assay, controls, replicate counts, concentration when measured, collector source, and provenance. A negative result does not prove absence, and a positive result does not by itself prove the exact source.", "", "## Environmental and One Health context", ""]
    lines += ["No environmental context records were collected during this deterministic reproduction." if not result["environmental_context"] else "Stored contextual records are included in the machine-readable output with their provider limitations."]
    lines += ["The One Health pathway is literature-linked monitoring relevance. It does not establish local parasite presence, fish disease, or human-health impact.", "", "## Provenance", "", "All required inputs passed their recorded SHA-256 checksums. Full hashes and API provenance are stored in `wigger_result.json`.", "", "## Scientific limitations", "", "- No calibrated eDNA transport, decay, dilution, or detection-probability model.", "- No verified replicate or laboratory assay metadata for H001.", "- Historical eDNA evidence remains UNKNOWN under the current compatibility catalog.", "- The pair-separation score measures topology-based discrimination only.", "- Counterfactual candidate outcomes are unknown.", "- Environmental providers are not invoked by this reproduction."]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--isolated", action="store_true", help="Use a local SQLite demonstration database")
    parser.add_argument("--output-dir", default=str(ROOT / "reproducibility_outputs"))
    args = parser.parse_args()
    checksums = verify_inputs()
    audit = {}
    if args.isolated:
        output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
        temporary_database = tempfile.TemporaryDirectory(prefix="wigger-reproduction-")
        os.environ["DATABASE_URL"] = f"sqlite:///{Path(temporary_database.name) / 'wigger_reproduction.db'}"
        os.environ["DEBUG"] = "false"
        sys.path.insert(0, str(ROOT / "backend"))
        from app.db.session import create_tables
        create_tables()
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        environment = os.environ.copy()
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=ROOT / "backend", env=environment,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
        )
        api = HttpApi(f"http://127.0.0.1:{port}")
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(f"Isolated API failed to start:\n{server.stderr.read()}")
                try:
                    api.call("GET", "/health")
                    break
                except Exception:
                    time.sleep(0.05)
            else:
                raise RuntimeError("Timed out waiting for isolated API startup")
            result = execute(api, checksums, audit)
        finally:
            server.terminate()
            try:
                server.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)
            temporary_database.cleanup()
    else:
        result = execute(HttpApi(args.base_url), checksums, audit)
        output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "wigger_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "wigger_scientific_result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "wigger_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "WIGGER_INVESTIGATION_REPORT.md").write_text(report(result), encoding="utf-8")
    print(json.dumps({"status": "PASS", "decision": result["registered_site_decision"]["status"], "output_dir": str(output_dir)}, indent=2))


if __name__ == "__main__": main()
