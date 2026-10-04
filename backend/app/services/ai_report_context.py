"""Read-only, versioned scientific snapshot and conservative narrative vocabulary.

Arbitrary evidence prose is never promoted to an approved scientific statement.
Fingerprints cover full relevant records locally; the provider gets only a
bounded projection, without collector details, raw GIS or arbitrary metadata.
"""
from collections import Counter
from datetime import date, datetime
from enum import Enum
from hashlib import sha256
import json
import re
from uuid import UUID

from sqlalchemy import select
from app.db.models import (CaseModel, SamplingSiteModel, EvidenceItemModel, CandidateZoneModel,
    SamplingDecisionModel, DecisionTraceModel, InvestigationRunModel, ReplicateObservationModel,
    HypothesisStateModel, FollowUpSampleModel, TargetSpeciesModel, ContextExecutionModel)
from app.repositories.detection_contexts import selected_context, scope_clause, belongs
from app.services.one_health_service import OneHealthService
from app.services.scientific_results import current_rule_versions
from app.services.openrouter_client import report_error
from app.schemas.ai_reports import SECTION_NAMES
from config import config

SNAPSHOT_VERSION = 'freshwater.ai_input.v1'
MAX_INPUT_BYTES = 100_000


def normalized(value):
    if isinstance(value, dict):
        return {str(k): normalized(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [normalized(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def fingerprint(value):
    return sha256(json.dumps(normalized(value), sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def record(row):
    return {column.name: getattr(row, column.key if column.name != 'meta' else 'meta')
            for column in row.__table__.columns}


def safe_text(value, limit=300):
    text = str(value)
    if config.OPENROUTER_API_KEY:
        text = text.replace(config.OPENROUTER_API_KEY, '[redacted]')
    text = re.sub(r'sk-[\w-]+|[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}|Bearer\s+\S+', '[redacted]', text)
    text = re.sub(r'/home/[^/\s]+/[^\s]*', '[local source file]', text)
    return text[:limit]


def safe_projection(value, depth=0):
    if depth > 10:
        return '[nested data omitted]'
    if isinstance(value, dict):
        return {str(k): safe_projection(v, depth + 1) for k, v in value.items()
                if not re.search(r'password|secret|token|key|collector|email|phone|address|name', str(k), re.I)}
    if isinstance(value, (list, tuple)):
        return [safe_projection(v, depth + 1) for v in value]
    return safe_text(value, 1500) if isinstance(value, str) else normalized(value)


def incomplete(message):
    raise report_error(409, 'AIIncompleteData', message)


def resolve(db, case_id):
    case = db.get(CaseModel, case_id)
    if case is None:
        raise report_error(404, 'NotFoundError', 'Investigation not found.')
    context = selected_context(db, case_id)
    if context is None:
        incomplete('A persisted detection context is required.')
    species = db.get(TargetSpeciesModel, context.species_id)
    site = db.get(SamplingSiteModel, context.site_id)
    if species is None or species.case_id != case_id or not belongs(db, site, case_id, physical_site=True):
        incomplete('Detection context has inconsistent ownership.')
    return case, context, species, site


def build_snapshot(db, case_id):
    case, context, species, site = resolve(db, case_id)

    def scoped(model):
        return list(db.scalars(select(model).where(model.case_id == case_id,
            scope_clause(db, model, case_id)).order_by(model.id)))

    evidence, zones = scoped(EvidenceItemModel), scoped(CandidateZoneModel)
    decision = db.scalar(select(SamplingDecisionModel).where(SamplingDecisionModel.case_id == case_id,
        scope_clause(db, SamplingDecisionModel, case_id)).order_by(SamplingDecisionModel.created_at.desc(), SamplingDecisionModel.id.desc()))
    if not evidence or not zones or decision is None:
        incomplete('Persisted evidence, source hypotheses and a scientific decision are required. Run the scientific workflow first.')
    trace = db.scalar(select(DecisionTraceModel).where(DecisionTraceModel.decision_id == decision.id))
    candidates = (decision.candidate_snapshot or {}).get('candidates')
    if trace is None or not isinstance(candidates, list):
        incomplete('The selected decision lacks a persisted trace or candidate comparison.')
    if not candidates and decision.status not in ('ABSTAIN', 'INSUFFICIENT_DATA'):
        incomplete('The selected decision requires a persisted candidate comparison.')
    evidence_ids = {str(e.id) for e in evidence}
    if any(str(i) not in evidence_ids for i in trace.evidence_used):
        incomplete('The decision trace references evidence outside this detection context.')
    run = db.scalar(select(InvestigationRunModel).where(InvestigationRunModel.new_decision_id == decision.id))
    if run is not None and (not belongs(db, run, case_id) or run.status != 'COMPLETED'):
        incomplete('Decision and completed investigation run do not belong together.')
    if decision.candidate_scope == 'GENERATED_REPRESENTATIVES' and run is None:
        incomplete('Generated decision has no associated completed investigation run.')
    candidate_records = []
    for item in candidates:
        try:
            candidate = db.get(SamplingSiteModel, UUID(str(item['site_id'])))
        except (KeyError, TypeError, ValueError):
            incomplete('Candidate identity is unavailable.')
        if not belongs(db, candidate, case_id, physical_site=True):
            incomplete('Candidate ownership does not match the selected context.')
        candidate_records.append(candidate)
    if not set(map(str, decision.recommended_site_ids)).issubset({str(c.id) for c in candidate_records}):
        incomplete('Decision alternatives are missing from the persisted comparison.')
    states = [] if run is None else list(db.scalars(select(HypothesisStateModel).where(
        HypothesisStateModel.investigation_run_id == run.id,
        HypothesisStateModel.case_id == case_id, scope_clause(db, HypothesisStateModel, case_id)).order_by(HypothesisStateModel.id)))
    replicates = list(db.scalars(select(ReplicateObservationModel).where(
        ReplicateObservationModel.case_id == case_id, ReplicateObservationModel.detection_context_id == context.id
    ).order_by(ReplicateObservationModel.evidence_id, ReplicateObservationModel.replicate_index)))
    if any(str(r.evidence_id) not in evidence_ids for r in replicates):
        incomplete('Replicate evidence ownership is inconsistent.')
    one_health = normalized(OneHealthService(db).assess(case_id))
    rule_versions = current_rule_versions(trace.rules_applied)
    # Full raw records are hashed locally only, never persisted in AI reports or sent to the provider.
    local = {'version': SNAPSHOT_VERSION, 'case': record(case), 'context': record(context),
        'species': record(species), 'site': record(site), 'evidence': [record(x) for x in evidence],
        'zones': [record(x) for x in zones], 'decision': record(decision), 'trace': record(trace),
        'run': record(run) if run else None, 'states': [record(x) for x in states],
        'candidates': [record(x) for x in candidate_records], 'replicates': [record(x) for x in replicates],
        'follow_up': [record(x) for x in scoped(FollowUpSampleModel)],
        'provider_executions': [record(x) for x in scoped(ContextExecutionModel)],
        'one_health': one_health, 'rules': rule_versions}
    bank = {name: [] for name in SECTION_NAMES}
    sources = {}

    def statement(section, text, reference, source):
        sources[reference] = source
        bank[section].append({'text': text, 'source_references': [reference]})

    summary, uncertainty, sampling, health = SECTION_NAMES
    statement(summary, f'The selected investigation concerns the recorded taxon {json.dumps(safe_text(species.taxon, 200))} on {context.sampled_on.isoformat()}.',
        f'context:{context.id}', {'kind': 'detection_context', 'species': safe_text(species.taxon, 200), 'date': context.sampled_on.isoformat()})
    statement(summary, f'The detection location is recorded at {site.latitude}, {site.longitude}, HydroRIVERS reach {site.hyriv_id}, with network status {site.validation_status}.',
        f'site:{site.id}', {'kind': 'physical_site', 'reach': site.hyriv_id, 'status': site.validation_status,
        'provenance': safe_projection({key: value for key, value in (site.meta or {}).items()
            if key in ('validation_method', 'validation_reason', 'network_source', 'artifact_sha256',
                       'doi', 'review_confirmed', 'location_match', 'selected_match')})})
    observation_details = []
    for e in evidence:
        ref = f'evidence:{e.id}'
        classification = ('VERIFIED_HISTORICAL_REFERENCE' if str(e.id) == str(one_health.get('reference_evidence_id'))
            else 'SYNTHETIC_TEST_DATA' if (e.provenance or {}).get('synthetic') or 'synthetic' in e.source.lower()
            else 'USER_REPORTED_UNVERIFIED')
        results = [r.result for r in replicates if r.evidence_id == e.id]
        counts = Counter(results)
        detail = {'kind': 'evidence', 'type': safe_text(e.evidence_type), 'classification': classification,
            'quality': safe_text(e.quality or 'UNASSESSED'), 'source': safe_text(e.source),
            'replicate_counts': {s: counts[s] for s in ('Positive', 'Negative', 'Invalid')} if results else None}
        assay = (e.value or {}).get('assay_metadata')
        detail['laboratory_metadata'] = (safe_projection({k: v for k, v in assay.items()
            if k in ('assay', 'method', 'controls_status', 'limit_of_detection', 'units')}) if isinstance(assay, dict) else None)
        observation_details.append(detail)
        if results:
            statement(summary, f'A {classification} observation records {counts["Positive"]} positive, {counts["Negative"]} negative and {counts["Invalid"]} invalid replicates. These recorded results do not establish independently verified laboratory evidence.', ref, detail)
            if counts['Positive'] and counts['Negative']:
                statement(uncertainty, 'Positive and negative replicates occur in the same recorded observation, so detection was inconsistent across those replicates. This does not provide a calibrated detection probability, and a negative replicate does not prove biological absence.', ref, detail)
        elif classification == 'VERIFIED_HISTORICAL_REFERENCE':
            detail['historical_measurement'] = safe_projection(e.value)
            detail['provenance'] = safe_projection(e.provenance)
            statement(summary, 'The observation has verified Carraro H001 historical provenance. Replicate-level results are unavailable for this historical observation; synthetic test replicates must not be substituted.', ref, detail)
            if (e.value or {}).get('concentration_mol_l') is not None:
                statement(summary, f'The verified historical observation records a concentration of {e.value["concentration_mol_l"]} mol/L. This measurement is not a population-abundance estimate.', ref, detail)
        elif e.evidence_type in ('edna_observation', 'historical_edna_measurement', 'follow_up_edna_sample'):
            statement(summary, f'An observation is recorded as {classification}; normalized replicate results are unavailable.', ref, detail)
        else:
            sources[ref] = detail
    for zone in zones:
        state = next((s.status for s in states if s.zone_id == zone.id), None)
        statement(summary, f'Source hypothesis {json.dumps(safe_text(zone.label))} has network status {zone.validation_status}; its persisted hypothesis state is {state or "unavailable"}.',
            f'zone:{zone.id}', {'kind': 'hypothesis', 'label': safe_text(zone.label), 'network_status': zone.validation_status, 'hypothesis_status': state})
    statement(uncertainty, 'Geographic matching and directed network connectivity do not independently verify biological presence, actual eDNA transport or the biological source. Unknown or unassessed evidence remains unresolved.',
        'method:scientific_boundary', {'kind': 'method', 'rule': 'hydrorivers.directed_contribution.v1'})
    statement(uncertainty, 'No calibrated detection probability, abundance estimate, transport or decay estimate, pollution conclusion, pathogen-presence conclusion or disease-risk estimate is established by this explanation.',
        'method:limits', {'kind': 'method', 'source': 'SCIENCE_FREEZE_v4.md'})
    assessments = [check for check in trace.hydrology_checks if check.get('check') == 'evidence_assessment']
    zone_by_id = {str(zone.id): zone for zone in zones}
    for check in assessments:
        for assessment in check.get('assessments', []):
            if str(assessment.get('evidence_id')) not in evidence_ids or str(assessment.get('zone_id')) not in zone_by_id:
                incomplete('A persisted assessment references evidence or a hypothesis outside this context.')
            zone = zone_by_id[str(assessment['zone_id'])]
            reference = f'assessment:{trace.id}:{zone.id}:{assessment["evidence_id"]}'
            statement(uncertainty, f'The stored assessment for hypothesis {json.dumps(safe_text(zone.label))} '
                f'records evidence compatibility {safe_text(assessment.get("compatibility", "UNKNOWN"))}. '
                f'Its recorded reason is {json.dumps(safe_text(assessment.get("reason", "unavailable"), 1500))}; '
                f'rule: {safe_text(assessment.get("rule_id") or "no validated rule applies")}.',
                reference, {'kind': 'evidence_assessment', **safe_projection(assessment)})
    statement(uncertainty, 'Only assessments and hypothesis states stored with the selected decision or its associated run are used. Missing persisted assessments or states are unavailable, not independently reassessed by AI.',
        f'trace:{trace.id}', {'kind': 'decision_trace', 'rules': trace.rules_applied, 'rule_versions': rule_versions,
            'assessments_available': bool(assessments), 'hypothesis_states_available': bool(states),
            'hydrology_checks': safe_projection(trace.hydrology_checks),
            'assumptions': safe_projection(trace.assumptions), 'limitations': safe_projection(trace.limitations),
            'hypothesis_states': safe_projection([{'zone_id': s.zone_id, 'status': s.status,
                'reason': s.reason, 'rule_ids': s.rule_ids, 'evidence_ids': s.evidence_ids} for s in states])})
    statement(sampling, f'The persisted scientific decision is {decision.status}, using candidate scope {decision.candidate_scope}.',
        f'decision:{decision.id}', {'kind': 'decision', 'status': decision.status, 'candidate_scope': decision.candidate_scope})
    if not candidates:
        statement(sampling, 'The persisted comparison contains no eligible candidates; no sampling location is recommended.',
            f'decision:{decision.id}', sources[f'decision:{decision.id}'])
    for item, candidate in zip(candidates, candidate_records):
        score = item.get('pair_separation_score')
        label = safe_text(item.get('label') or candidate.label)
        winner = candidate.id in decision.recommended_site_ids
        statement(sampling, f'Candidate {json.dumps(label)} on reach {item.get("hyriv_id")} has recorded pair-separation score {score if score is not None else "unavailable"}'
            + (' and is one of the tied alternatives.' if winner and decision.status == 'TIE' else ' and is a recorded recommendation.' if winner else '.'),
            f'candidate:{candidate.id}', {'kind': 'candidate', 'label': label, 'reach': item.get('hyriv_id'),
                'score': score, 'recommended': winner})
    statement(sampling, 'Pair separation counts hypothesis pairs distinguished under the existing ideal binary-outcome assumptions. It is not a probability of successful detection and does not establish accessibility, cost or practical suitability.',
        'method:pair_separation', {'kind': 'method', 'rule': 'sampling.topology_pair_separation.v1'})
    if decision.status == 'TIE':
        statement(sampling, 'The tied alternatives remain a TIE under the recorded criterion; this explanation does not select a preferred site.', f'decision:{decision.id}', sources[f'decision:{decision.id}'])
    statement(health, 'The eDNA observation alone does not demonstrate pollution, pathogen presence, fish disease, human-health risk or population abundance. Literature relationships are not proof of effects observed in this investigation.',
        'method:one_health_boundary', {'kind': 'method', 'source': 'SCIENCE_FREEZE_v4.md'})
    if not one_health['pathways']:
        statement(health, 'No verified species-specific One Health pathway is available for this detection context. Environmental and health implications remain unresolved.',
            'one_health:availability', {'kind': 'one_health', 'status': 'UNKNOWN'})
    for pathway in one_health['pathways']:
        for name, claim in pathway.items():
            if isinstance(claim, dict) and 'statement' in claim and 'status' in claim:
                statement(health, f'{claim["status"]}: {claim["statement"]}', f'claim:{pathway["pathway_id"]}:{name}',
                    {'kind': 'one_health_claim', **claim, 'scientific_sources': pathway['scientific_sources'], 'limitations': pathway['limitations']})
    snapshot = {'version': SNAPSHOT_VERSION, 'case_id': str(case_id), 'detection_context_id': str(context.id),
        'decision_id': str(decision.id), 'investigation_run_id': str(run.id) if run else None,
        'species': safe_text(species.taxon, 200), 'observation_date': context.sampled_on.isoformat(),
        'decision_status': decision.status, 'observations': observation_details,
        'statements': bank, 'sources': sources,
        'input_fingerprint': fingerprint(local)}
    # Free-form strings in the source index are data, never model instructions.
    encoded = json.dumps(snapshot, ensure_ascii=True, allow_nan=False)
    if config.OPENROUTER_API_KEY and config.OPENROUTER_API_KEY in encoded:
        incomplete('A source record contains sensitive content and cannot be sent to AI.')
    if len(encoded.encode()) > MAX_INPUT_BYTES or any(len(v) > 100 for v in bank.values()):
        incomplete('Scientific input exceeds the bounded AI report size. Use the deterministic report.')
    return snapshot
