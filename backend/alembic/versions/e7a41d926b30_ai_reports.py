"""Add append-only AI explanation drafts; leave scientific records untouched."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = 'e7a41d926b30'
down_revision = 'd4e93b7a2601'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('ai_reports',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('case_id', sa.UUID(), sa.ForeignKey('cases.id'), nullable=False),
        sa.Column('detection_context_id', sa.UUID(), nullable=False),
        sa.Column('decision_id', sa.UUID(), sa.ForeignKey('sampling_decisions.id'), nullable=False),
        sa.Column('investigation_run_id', sa.UUID(), sa.ForeignKey('investigation_runs.id'), nullable=True),
        sa.Column('input_fingerprint', sa.String(64), nullable=False),
        sa.Column('prompt_version', sa.String(100), nullable=False),
        sa.Column('model_identifier', sa.String(150), nullable=False),
        sa.Column('narrative', JSONB(), nullable=False),
        sa.Column('sources', JSONB(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('validation_status', sa.String(30), nullable=False),
        sa.Column('review_status', sa.String(30), nullable=False),
        sa.ForeignKeyConstraint(['detection_context_id', 'case_id'], ['detection_contexts.id', 'detection_contexts.case_id']))
    op.create_index('ix_ai_reports_case_context_generated', 'ai_reports', ['case_id', 'detection_context_id', 'generated_at'])


def downgrade():
    op.drop_index('ix_ai_reports_case_context_generated', table_name='ai_reports')
    op.drop_table('ai_reports')
