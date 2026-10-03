"""Record decision candidate scope without changing historical scientific outputs."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f1a2b3c4d5e6"
down_revision = "d4c8e1a907b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sampling_decisions", sa.Column(
        "candidate_scope", sa.String(50), nullable=False, server_default="REGISTERED_SITES",
    ))
    op.add_column("sampling_decisions", sa.Column(
        "candidate_snapshot", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=False, server_default=sa.text("'{}'"),
    ))
    op.execute(sa.text("""
        UPDATE sampling_decisions SET candidate_scope = 'GENERATED_REPRESENTATIVES'
        WHERE EXISTS (
            SELECT 1 FROM investigation_runs
            WHERE investigation_runs.new_decision_id = sampling_decisions.id
        )
    """))


def downgrade():
    op.drop_column("sampling_decisions", "candidate_snapshot")
    op.drop_column("sampling_decisions", "candidate_scope")
