"""Add structured follow-up samples.

Revision ID: a31f6c729d0a
Revises: 6758ca39bed9
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a31f6c729d0a"
down_revision: Union[str, None] = "6758ca39bed9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "follow_up_samples",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sampling_site_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("candidate_reference", sa.String(200), nullable=True),
        sa.Column("hyriv_id", sa.Integer(), nullable=False),
        sa.Column("sampled_at", sa.DateTime(), nullable=False),
        sa.Column("replicate_count", sa.Integer(), nullable=False),
        sa.Column("positive_replicates", sa.Integer(), nullable=False),
        sa.Column("concentration", sa.Float(), nullable=True),
        sa.Column("concentration_unit", sa.String(100), nullable=True),
        sa.Column("assay", sa.String(200), nullable=False),
        sa.Column("controls_status", sa.String(100), nullable=False),
        sa.Column("collector_source", sa.String(200), nullable=False),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("evidence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["sampling_site_id"], ["sampling_sites.id"]),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence_items.id"]),
    )


def downgrade() -> None:
    op.drop_table("follow_up_samples")
