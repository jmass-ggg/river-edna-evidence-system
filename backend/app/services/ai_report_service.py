"""Versioned draft lifecycle. No scientific engines are executed here."""
from datetime import datetime, timezone
from sqlalchemy import select
from fastapi import HTTPException
from app.db.models import AIReportModel
from app.services.ai_report_context import build_snapshot, resolve
from app.services.ai_report_validator import validate_narrative, SYSTEM_PROMPT, PROMPT_VERSION
from app.services.openrouter_client import OpenRouterClient, report_error
from app.schemas.ai_reports import AINarrative, AIReportResponse, AIReportLatest
from config import config


class AIReportService:
    def __init__(self, db, client=None):
        self.db = db
        self.client = client or OpenRouterClient()

    def generate(self, case_id):
        self.client.require_configuration()
        snapshot = build_snapshot(self.db, case_id)
        raw = self.client.generate(snapshot, SYSTEM_PROMPT, AINarrative.model_json_schema())
        narrative = validate_narrative(raw, snapshot)
        # Refresh persisted state after the external call; never approve a
        # snapshot that changed while the provider was generating prose.
        self.db.rollback()
        current = build_snapshot(self.db, case_id)
        if current['input_fingerprint'] != snapshot['input_fingerprint']:
            raise report_error(409, 'AIStaleReport', 'Scientific inputs changed during generation. Regenerate the explanation.')
        from uuid import UUID
        row = AIReportModel(case_id=case_id, detection_context_id=UUID(snapshot['detection_context_id']),
            decision_id=UUID(snapshot['decision_id']),
            investigation_run_id=UUID(snapshot['investigation_run_id']) if snapshot['investigation_run_id'] else None,
            input_fingerprint=snapshot['input_fingerprint'], prompt_version=PROMPT_VERSION,
            model_identifier=self.client.settings.OPENROUTER_MODEL,
            narrative=narrative.model_dump(mode='json'), sources=snapshot['sources'],
            validation_status='VALIDATED', review_status='DRAFT')
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.serialize(row, True)

    def is_current(self, row):
        try:
            snapshot = build_snapshot(self.db, row.case_id)
            return (row.prompt_version == PROMPT_VERSION and row.input_fingerprint == snapshot['input_fingerprint']
                and str(row.decision_id) == snapshot['decision_id']
                and (str(row.investigation_run_id) if row.investigation_run_id else None) == snapshot['investigation_run_id']
                and str(row.detection_context_id) == snapshot['detection_context_id'])
        except HTTPException as exc:
            if exc.status_code in (404, 409):
                return False
            raise

    def latest(self, case_id):
        _, context, _, _ = resolve(self.db, case_id)
        # Disabled installations do not need a report table to render the
        # deterministic report, and disabled AI text must never be exported.
        if not config.AI_REPORTS_ENABLED:
            return AIReportLatest(enabled=False, available=False, report=None)
        row = self.db.scalar(select(AIReportModel).where(AIReportModel.case_id == case_id,
            AIReportModel.detection_context_id == context.id).order_by(AIReportModel.generated_at.desc(), AIReportModel.id.desc()))
        return AIReportLatest(enabled=True, available=self.client.configured(),
            report=self.serialize(row, self.is_current(row)) if row else None)

    def approve(self, case_id, report_id):
        if not config.AI_REPORTS_ENABLED:
            raise report_error(503, 'AIUnavailable', 'AI reports are disabled.')
        _, context, _, _ = resolve(self.db, case_id)
        row = self.db.scalar(select(AIReportModel).where(AIReportModel.id == report_id,
            AIReportModel.case_id == case_id, AIReportModel.detection_context_id == context.id).with_for_update())
        if row is None:
            raise report_error(404, 'NotFoundError', 'AI report not found in the selected context.')
        if not self.is_current(row):
            raise report_error(409, 'AIStaleReport', 'Scientific inputs changed. Regenerate and review a current draft.')
        # Revalidate persisted text as well as the fingerprint before approval.
        import json
        validate_narrative(json.dumps(row.narrative), build_snapshot(self.db, case_id))
        if row.review_status != 'APPROVED':
            row.review_status = 'APPROVED'
            row.reviewed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            self.db.commit()
            self.db.refresh(row)
        return self.serialize(row, True)

    @staticmethod
    def serialize(row, current):
        return AIReportResponse(id=row.id, case_id=row.case_id, detection_context_id=row.detection_context_id,
            decision_id=row.decision_id, investigation_run_id=row.investigation_run_id,
            input_fingerprint=row.input_fingerprint, prompt_version=row.prompt_version,
            model_identifier=row.model_identifier, generated_at=row.generated_at, reviewed_at=row.reviewed_at,
            validation_status=row.validation_status, review_status=row.review_status,
            current=current, stale=not current,
            exportable=bool(config.AI_REPORTS_ENABLED and current and row.review_status == 'APPROVED'),
            narrative=row.narrative, sources=row.sources)
