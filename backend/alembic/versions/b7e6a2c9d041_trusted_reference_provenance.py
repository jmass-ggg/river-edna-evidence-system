"""Separate server-loaded reference provenance from caller-owned metadata.

Legacy rows intentionally remain untrusted; matching metadata is not proof
that they were created by the reference loader.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7e6a2c9d041"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("cases", sa.Column("reference_key", sa.String(100), nullable=True))
    op.add_column("cases", sa.Column(
        "reference_provenance", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
        nullable=True,
    ))
    op.create_unique_constraint("uq_cases_reference_key", "cases", ["reference_key"])


def downgrade():
    op.drop_constraint("uq_cases_reference_key", "cases", type_="unique")
    op.drop_column("cases", "reference_provenance")
    op.drop_column("cases", "reference_key")
