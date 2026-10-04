"""Persist provider execution outcomes independently of evidence."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c9d42e8a710f"
down_revision = "b7e6a2c9d041"
branch_labels = None
depends_on = None


def upgrade():
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
    op.create_table("context_executions",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("case_id", sa.UUID(), sa.ForeignKey("cases.id"), nullable=False),
        sa.Column("evidence_id", sa.UUID(), sa.ForeignKey("evidence_items.id")),
        sa.Column("provider", sa.String(200), nullable=False),
        sa.Column("evidence_type", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("data", json_type),
        sa.Column("provenance", json_type, nullable=False),
        sa.Column("limitations", json_type, nullable=False),
        sa.Column("request", json_type, nullable=False),
        sa.Column("error", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_context_executions_case_id", "context_executions", ["case_id"])


def downgrade():
    op.drop_table("context_executions")
