from app.repositories.detection_contexts import belongs, selected_context, scope_clause
"""Explicit, versioned orchestration of existing scientific components."""
from datetime import datetime
from copy import deepcopy
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.db.models import (
    CandidateZoneModel, DecisionTraceModel, EvidenceItemModel,
    FollowUpSampleModel, GeneratedCandidateSnapshotModel, HypothesisStateModel,
    InvestigationRunModel, SamplingDecisionModel,
)
from app.domain.enums import (
    HypothesisStatus, InvestigationRunStatus, InvestigationTriggerType, ValidationStatus,
)
from app.repositories.cases import CaseRepository, CaseNotFoundError
from app.repositories.evidence import EvidenceRepository
from app.repositories.investigations import InvestigationRepository
from app.repositories.sampling import SamplingRepository
from app.services.scientific_results import canonical_scientific_result, reference_identities, current_rule_versions


class InvestigationService:
    def __init__(
        self, db, evidence_engine, hypothesis_resolver, candidate_generator,
        sampling_engine, site_a_fraction: float = 1.0,
    ):
        self.db = db
        self.evidence_engine = evidence_engine
        self.hypothesis_resolver = hypothesis_resolver
        self.candidate_generator = candidate_generator
        self.sampling_engine = sampling_engine
        self.site_a_fraction = site_a_fraction
        self.runs = InvestigationRepository(db)

    @staticmethod
    def require_decision_prerequisites(db, case):
        """Check investigation ownership and detection/evidence before scoring."""
        repository = SamplingRepository(db)
        detection = repository.get_site_by_id(case.detection_site_id)
        evidence = EvidenceRepository(db).get_evidence_by_case(case.id)
        missing = []
        if detection.case_id != case.id:
            missing.append("Detection site does not belong to this investigation")
        if detection.validation_status not in (ValidationStatus.MATCHED, ValidationStatus.VERIFIED):
            missing.append(detection.metadata.get("validation_reason") or "Detection location requires supported network validation")
        from app.services.evidence_service import EvidenceService
        if not any(EvidenceService.qualifying_observation(item) for item in evidence):
            missing.append("Recorded biological observation evidence and provenance are missing; context and topology alone do not qualify")
        if not repository.get_zones_by_case(case.id):
            missing.append("Source hypotheses are missing")
        if missing:
            raise HTTPException(status_code=422, detail={
                "type": "IncompleteScientificPrerequisites", "message": "; ".join(missing),
                "missing": missing,
            })
        return evidence

    def reinvestigate(
        self, case_id: UUID, trigger_evidence_id: UUID | None = None,
        trigger_follow_up_sample_id: UUID | None = None,
    ) -> dict:
        from app.services.case_service import CaseService
        case = CaseService(CaseRepository(self.db)).get_case(case_id)
        trigger_type = self._validate_trigger(case_id, trigger_evidence_id, trigger_follow_up_sample_id)
        self.require_decision_prerequisites(self.db, case)
        previous_decision = self.db.scalar(
            select(SamplingDecisionModel).where(SamplingDecisionModel.case_id == case_id, scope_clause(self.db, SamplingDecisionModel, case_id))
            .order_by(SamplingDecisionModel.created_at.desc(), SamplingDecisionModel.id.desc()).limit(1)
        )
        run = self.runs.create_running(
            case_id, trigger_type, trigger_evidence_id, trigger_follow_up_sample_id,
            previous_decision.id if previous_decision else None,
        )
        try:
            evidence = EvidenceRepository(self.db).get_evidence_by_case(case_id)
            zones = SamplingRepository(self.db).get_zones_by_case(case_id)
            states = []
            hypothesis_snapshot = []
            assessment_rule_ids = set()
            for zone in zones:
                assessments = self.evidence_engine.assess_evidence_for_zone(case, zone, evidence, [])
                summary = self.evidence_engine.summarize_zone_assessment(assessments)
                status, reason = self.hypothesis_resolver.resolve(zone, assessments, summary)
                assessment_rule_ids.update(item.rule_id for item in assessments if item.rule_id)
                state = HypothesisStateModel(
                    investigation_run_id=run.id, case_id=case_id, zone_id=zone.id,
                    zone_label=zone.label, status=status.value, reason=reason,
                    support_count=summary["supports"], contradict_count=summary["contradicts"],
                    neutral_count=summary["neutral"], unknown_count=summary["unknown"],
                    evidence_ids=[item.evidence_id for item in assessments],
                    rule_ids=sorted({item.rule_id for item in assessments if item.rule_id}),
                )
                states.append(state)
                hypothesis_snapshot.append({"zone_id": str(zone.id), "zone_label": zone.label, "status": status.value, "reason": reason, **summary})

            detection_site = SamplingRepository(self.db).get_site_by_id(case.detection_site_id)
            eligible_zones = [
                zone for zone, snapshot in zip(zones, hypothesis_snapshot)
                if not hasattr(self.hypothesis_resolver, "eligible")
                or self.hypothesis_resolver.eligible(HypothesisStatus(snapshot["status"]))
            ]
            if not eligible_zones:
                eligible_zones = zones
            from app.services.sampling_service import detection_fraction
            selected_fraction = detection_fraction(detection_site, self.site_a_fraction)
            generated = self.candidate_generator.generate(
                eligible_zones, detection_site.hyriv_id, site_a_fraction=selected_fraction
            )
            snapshots = []
            transient_sites = []
            for candidate in generated.candidates:
                site = SamplingRepository(self.db).persist_generated_site(case_id, candidate)
                transient_sites.append(site)
                snapshots.append(GeneratedCandidateSnapshotModel(
                    investigation_run_id=run.id, case_id=case_id,
                    hyriv_id=candidate.hyriv_id, signature=candidate.signature,
                    pair_separation_score=candidate.pair_separation_score,
                    equivalence_class=candidate.equivalence_class,
                    equivalent_hyriv_ids=candidate.equivalent_hyriv_ids,
                    network_distance_km=candidate.network_distance_km,
                    selection_reason=candidate.selection_reason,
                    validation_status=candidate.validation_status.value,
                ))

            evaluations = self.sampling_engine.evaluate_candidates(case, eligible_zones, transient_sites, self.candidate_generator.hydrology_engine)
            decision_status, recommended_ids, rationale = self.sampling_engine.make_recommendation(evaluations)
            decision = SamplingDecisionModel(case_id=case_id, status=decision_status.value, recommended_site_ids=recommended_ids, rationale=rationale, candidate_scope="GENERATED_REPRESENTATIVES")
            self.db.add(decision)
            self.db.flush()
            trace = self.sampling_engine.create_decision_trace(case, evaluations, decision_status, recommended_ids, decision.id)
            reasoning_checks = [
                {"check": "hypothesis_state_reasoning", "states": hypothesis_snapshot},
                {
                    "check": "candidate_generation_criterion",
                    "rule": "sampling.topology_pair_separation.v1",
                    "eligible_zone_labels": [zone.label for zone in eligible_zones],
                    "all_unknown_preserves_candidate_set": all(
                        item["status"] == HypothesisStatus.UNKNOWN.value for item in hypothesis_snapshot
                    ),
                },
            ]
            has_follow_up = any(item.evidence_type == "follow_up_edna_sample" for item in evidence)
            trace_model = DecisionTraceModel(
                decision_id=decision.id, evidence_used=[item.id for item in evidence],
                rules_applied=sorted(set(trace.rules_applied) | assessment_rule_ids),
                hydrology_checks=[*trace.hydrology_checks, *reasoning_checks],
                assumptions=[*trace.assumptions, f"InvestigationRun: {run.id}"],
                limitations=[
                    *trace.limitations,
                    "Hypothesis states use validated directional rules only; V4 defines no elimination criterion.",
                    *(["New follow-up sample recorded, but no validated interpretation rule currently allows this observation to alter source hypotheses."] if has_follow_up else []),
                ],
            )
            trace_model.hydrology_checks = [*trace_model.hydrology_checks, {
                "check": "scientific_rule_versions", "versions": current_rule_versions(trace_model.rules_applied)}]
            candidate_snapshot = {
                "detection_hyriv_id": detection_site.hyriv_id,
                "detection_position_fraction": selected_fraction,
                "detection_position_method": (
                    "Frozen Site A reference position" if (detection_site.metadata or {}).get("network_source", "").endswith("site_a.json")
                    else "Reviewed geometry-derived position" if (detection_site.metadata or {}).get("selected_match", {}).get("fraction_along_reach") is not None
                    else "Estimated reach midpoint (fraction 0.5); precise detection position unavailable"
                ),
                "eligible_reach_count": generated.eligible_reach_count,
                "hypothesis_labels": generated.hypothesis_labels,
                "limitation": generated.limitation,
                "candidates": [{
                    "site_id": str(site.id), "hyriv_id": c.hyriv_id,
                    "latitude": c.latitude, "longitude": c.longitude,
                    "signature": c.signature, "pair_separation_score": c.pair_separation_score,
                    "equivalence_class": c.equivalence_class,
                    "network_distance_km": c.network_distance_km,
                    "network_distance_status": "ESTIMATED",
                    "network_distance_method": "Directed HydroRIVERS LENGTH_KM from generated reach midpoint (fraction 0.5) to configured detection fraction; representative is not a measured field position.",
                    "validation_status": c.validation_status.value,
                    "distinguished_hypothesis_pairs": [
                        [generated.hypothesis_labels[left], generated.hypothesis_labels[right]]
                        for left in range(len(c.signature)) for right in range(left + 1, len(c.signature))
                        if c.signature[left] != c.signature[right]
                    ],
                } for c, site in zip(generated.candidates, transient_sites)],
            }
            decision.candidate_snapshot = candidate_snapshot
            run_db = self.db.get(InvestigationRunModel, run.id)
            run_db.status = InvestigationRunStatus.COMPLETED.value
            run_db.completed_at = datetime.utcnow()
            run_db.new_decision_id = decision.id
            run_db.evidence_count = len(evidence)
            run_db.hypothesis_snapshot = {"states": hypothesis_snapshot}
            run_db.candidate_snapshot = candidate_snapshot
            run_db.decision_snapshot = {"id": str(decision.id), "candidate_scope": "GENERATED_REPRESENTATIVES", "status": decision_status.value, "recommended_site_ids": [str(value) for value in recommended_ids], "rationale": rationale}
            run_db.meta = {
                "resolver": getattr(self.hypothesis_resolver, "version", "unknown"),
                "follow_up_interpretation": "UNKNOWN_UNASSESSED" if has_follow_up else "NOT_APPLICABLE",
            }
            from dataclasses import asdict
            from app.scientific.rules.catalog import get_rule_catalog, get_strength_rule_catalog
            identities = reference_identities([asdict(site) for site in [detection_site, *transient_sites]],
                [asdict(zone) for zone in zones], [asdict(item) for item in evidence])
            run_db.meta = {**run_db.meta, "scientific_result": canonical_scientific_result({
                "case": {"target_taxon": case.target_taxon, "observation_date": case.observation_date,
                         "detection_site": asdict(detection_site)},
                "source_hypotheses": [asdict(zone) for zone in zones],
                "hypotheses": hypothesis_snapshot, "candidate_generation": candidate_snapshot,
                "sampling_decision": run_db.decision_snapshot,
                "evidence": [asdict(item) for item in evidence],
                "rules": [*get_rule_catalog(), *get_strength_rule_catalog()],
                "resolver": run_db.meta["resolver"],
                "input_provenance": getattr(self.evidence_engine, "graph_provenance", {}),
                "trace": {"rules_applied": trace_model.rules_applied, "hydrology_checks": trace_model.hydrology_checks,
                          "assumptions": trace_model.assumptions, "limitations": trace_model.limitations},
            }, identities)}
            self.db.add_all([*states, *snapshots, trace_model])
            self.db.commit()
            return self.detail(case_id, run.id)
        except Exception as exc:
            self.runs.mark_failed(run.id, str(exc))
            raise

    def _validate_trigger(self, case_id, evidence_id, sample_id):
        if evidence_id and sample_id:
            raise HTTPException(status_code=422, detail={"type": "ValidationError", "message": "Provide at most one reinvestigation trigger"})
        if evidence_id:
            item = self.db.get(EvidenceItemModel, evidence_id)
            if not belongs(self.db, item, case_id):
                raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Trigger evidence does not belong to case"})
            return InvestigationTriggerType.EVIDENCE
        if sample_id:
            item = self.db.get(FollowUpSampleModel, sample_id)
            if not belongs(self.db, item, case_id):
                raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Trigger follow-up sample does not belong to case"})
            return InvestigationTriggerType.FOLLOW_UP_SAMPLE
        return InvestigationTriggerType.MANUAL

    def list(self, case_id: UUID) -> list[dict]:
        from app.services.case_service import CaseService
        CaseService(CaseRepository(self.db)).get_case(case_id)
        return [self._summary(run) for run in self.runs.list_for_case(case_id)]

    def detail(self, case_id: UUID, run_id: UUID) -> dict:
        run = self.runs.get_for_case(case_id, run_id)
        if run is None:
            raise HTTPException(status_code=404, detail={"type": "NotFoundError", "message": "Investigation run not found"})
        prior = self.runs.latest_completed(case_id, exclude_run_id=run_id, before_started_at=run.started_at)
        hypotheses = (run.hypothesis_snapshot or {}).get("states", [])
        candidates = deepcopy(run.candidate_snapshot or {})
        decision = deepcopy(run.decision_snapshot or {})
        compatibility = self._historical_availability(run)
        prior_compatibility = self._historical_availability(prior) if prior else None
        comparison_status = ("FIRST_RUN" if prior is None else "AVAILABLE" if
            compatibility["status"] == "COMPLETE" and prior_compatibility["status"] == "COMPLETE" else "UNAVAILABLE_HISTORY")
        changed = {
            "hypotheses_changed": prior is None or self._hypothesis_signature(prior.hypothesis_snapshot) != self._hypothesis_signature(run.hypothesis_snapshot),
            "candidates_changed": prior is None or canonical_scientific_result(prior.candidate_snapshot) != canonical_scientific_result(run.candidate_snapshot),
            "decision_changed": prior is None or self._decision_signature(prior.decision_snapshot) != self._decision_signature(run.decision_snapshot),
        }
        changed["overall"] = any(changed.values())
        before = self._result_snapshot(prior) if prior else {}
        after = self._result_snapshot(run)
        change_reason = (
            "No scientifically supported hypothesis, candidate, or decision change occurred."
            if not changed["overall"]
            else "One or more versioned investigation outputs differ from the previous completed run."
        )
        if comparison_status == "UNAVAILABLE_HISTORY":
            change_reason = "Historical comparison is unavailable or incomplete; scientifically unchanged results cannot be established."
        elif comparison_status == "FIRST_RUN":
            change_reason = "No prior completed run is available for comparison."
        return {
            **self._summary(run), "hypotheses": hypotheses,
            "candidate_generation": candidates, "sampling_decision": decision,
            "decision_trace": self._trace(run.new_decision_id, case_id),
            "before": before, "after": after,
            "changed": changed, "change_reason": change_reason,
            "compatibility": compatibility,
            "change_comparison_status": comparison_status,
            "scientific_result": deepcopy((run.meta or {}).get("scientific_result", {})),
        }

    def _historical_availability(self, run):
        """Describe stored history without borrowing today's generated outputs."""
        candidate_snapshot = run.candidate_snapshot or {}
        candidates = candidate_snapshot.get("candidates")
        decision = self.db.get(SamplingDecisionModel, run.new_decision_id) if run.new_decision_id else None
        decision_owned = decision is not None and decision.case_id == run.case_id
        trace = self._trace(run.new_decision_id, run.case_id)
        references = []

        def reference(value, hyriv_id=None):
            return SamplingRepository(self.db).site_reference_status(value, run.case_id, hyriv_id)

        if isinstance(candidates, list):
            for index, candidate in enumerate(candidates):
                if not isinstance(candidate, dict):
                    references.append({"candidate_index": index, "status": "INVALID_SNAPSHOT"})
                    continue
                references.append({"candidate_index": index, "site_id": candidate.get("site_id"),
                                   "status": reference(candidate.get("site_id"), candidate.get("hyriv_id"))})
        comparison_complete = SamplingRepository.candidate_comparison_available(candidates)
        recommended = [{"site_id": str(value), "status": reference(value)}
                       for value in (run.decision_snapshot or {}).get("recommended_site_ids", [])]
        if not recommended and decision_owned:
            # Identity checks may inspect the persisted decision, but missing
            # historical snapshots are never filled with that or current scores.
            recommended = [{"site_id": str(value), "status": reference(value)}
                           for value in decision.recommended_site_ids]
        issues = []
        if not comparison_complete:
            issues.append("Historical candidate comparison is missing or incomplete; it was not reconstructed.")
        if any(item["status"] != "AVAILABLE" for item in [*references, *recommended]):
            issues.append("Historical candidate identities are missing or do not resolve within this case.")
        if not decision_owned:
            issues.append("The linked historical decision is unavailable or belongs to another case.")
        if not (run.decision_snapshot or {}).get("candidate_scope"):
            issues.append("Historical decision scope is unavailable; no current scope was substituted.")
        if trace is None:
            issues.append("Historical decision trace is unavailable; no trace was reconstructed.")
        return {
            "status": "PARTIAL" if issues else "COMPLETE",
            "historical_data_only": True,
            "candidate_comparison_available": comparison_complete,
            "candidate_references": references, "recommended_references": recommended,
            "decision_available": decision_owned, "decision_trace_available": trace is not None,
            "limitations": issues,
        }

    @staticmethod
    def _result_snapshot(run):
        return {
            "hypothesis_states": (run.hypothesis_snapshot or {}).get("states", []),
            "candidate_representatives": [
                item.get("hyriv_id") for item in (run.candidate_snapshot or {}).get("candidates", []) if isinstance(item, dict)
            ],
            "decision": run.decision_snapshot,
        }

    @staticmethod
    def _decision_signature(snapshot):
        """Compare scope and stable recommended identities as well as status."""
        snapshot = snapshot or {}
        return {
            "status": snapshot.get("status"),
            "rationale": snapshot.get("rationale"),
            "candidate_scope": snapshot.get("candidate_scope"),
            "recommended_site_ids": sorted(snapshot.get("recommended_site_ids", [])),
        }

    @staticmethod
    def _hypothesis_signature(snapshot):
        """Compare resolved states while retaining counts in the audit snapshot."""
        return sorted([
            (item.get("zone_label"), item.get("status"), item.get("reason"))
            for item in (snapshot or {}).get("states", [])
        ], key=lambda item: str(item[0]))

    @staticmethod
    def _summary(run):
        return {
            "investigation_run_id": run.id, "case_id": run.case_id,
            "status": run.status, "trigger_type": run.trigger_type,
            "trigger_evidence_id": run.trigger_evidence_id,
            "trigger_follow_up_sample_id": run.trigger_follow_up_sample_id,
            "previous_decision_id": run.previous_decision_id,
            "new_decision_id": run.new_decision_id, "evidence_count": run.evidence_count,
            "started_at": run.started_at, "completed_at": run.completed_at,
            "failure_reason": run.failure_reason, "metadata": run.meta,
        }

    def _trace(self, decision_id, case_id=None):
        if decision_id is None:
            return None
        decision = self.db.get(SamplingDecisionModel, decision_id)
        if decision is None or (case_id is not None and not belongs(self.db, decision, case_id)):
            return None
        trace = self.db.scalar(select(DecisionTraceModel).where(DecisionTraceModel.decision_id == decision_id))
        return {"decision_id": trace.decision_id, "created_at": trace.created_at,
                "rule_versions": next((check["versions"] for check in trace.hydrology_checks
                    if check.get("check") == "scientific_rule_versions"), {}),
                "evidence_used": trace.evidence_used, "rules_applied": trace.rules_applied,
                "hydrology_checks": trace.hydrology_checks, "assumptions": trace.assumptions,
                "limitations": trace.limitations} if trace else None
