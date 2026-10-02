"""Add versioned investigation history.

Revision ID: d4c8e1a907b2
Revises: a31f6c729d0a
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4c8e1a907b2"
down_revision: Union[str, None] = "a31f6c729d0a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trigger_type", sa.String(50), nullable=False),
        sa.Column("trigger_evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_follow_up_sample_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("previous_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("new_decision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_count", sa.Integer(), nullable=False),
        sa.Column("hypothesis_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("candidate_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("decision_snapshot", postgresql.JSONB(), nullable=False),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("meta", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["trigger_evidence_id"], ["evidence_items.id"]),
        sa.ForeignKeyConstraint(["trigger_follow_up_sample_id"], ["follow_up_samples.id"]),
        sa.ForeignKeyConstraint(["previous_decision_id"], ["sampling_decisions.id"]),
        sa.ForeignKeyConstraint(["new_decision_id"], ["sampling_decisions.id"]),
    )
    op.create_table(
        "hypothesis_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("investigation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("zone_label", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("support_count", sa.Integer(), nullable=False),
        sa.Column("contradict_count", sa.Integer(), nullable=False),
        sa.Column("neutral_count", sa.Integer(), nullable=False),
        sa.Column("unknown_count", sa.Integer(), nullable=False),
        sa.Column("evidence_ids", postgresql.JSONB(), nullable=False),
        sa.Column("rule_ids", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["investigation_run_id"], ["investigation_runs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["zone_id"], ["candidate_zones.id"]),
    )
    op.create_table(
        "generated_candidate_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("investigation_run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("hyriv_id", sa.Integer(), nullable=False),
        sa.Column("signature", postgresql.JSONB(), nullable=False),
        sa.Column("pair_separation_score", sa.Integer(), nullable=False),
        sa.Column("equivalence_class", sa.String(200), nullable=False),
        sa.Column("equivalent_hyriv_ids", postgresql.JSONB(), nullable=False),
        sa.Column("network_distance_km", sa.Float(), nullable=False),
        sa.Column("selection_reason", sa.Text(), nullable=False),
        sa.Column("validation_status", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["investigation_run_id"], ["investigation_runs.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
    )


def downgrade() -> None:
    op.drop_table("generated_candidate_snapshots")
    op.drop_table("hypothesis_states")
    op.drop_table("investigation_runs")
