"""Initial schema with all tables

Revision ID: 6758ca39bed9
Revises: 
Create Date: 2026-09-30 20:49:43.653065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6758ca39bed9'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create sampling_sites table first (no foreign key dependencies)
    op.create_table(
        'sampling_sites',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('hyriv_id', sa.Integer(), nullable=False),
        sa.Column('site_type', sa.String(length=50), nullable=False),
        sa.Column('validation_status', sa.String(length=50), nullable=False),
        sa.Column('network_latitude', sa.Float(), nullable=True),
        sa.Column('network_longitude', sa.Float(), nullable=True),
        sa.Column('snap_distance_m', sa.Float(), nullable=True),
        sa.Column('role', sa.String(length=100), nullable=True),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create cases table
    op.create_table(
        'cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('target_taxon', sa.String(length=200), nullable=False),
        sa.Column('observation_date', sa.Date(), nullable=False),
        sa.Column('detection_site_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['detection_site_id'], ['sampling_sites.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Add foreign key from sampling_sites to cases (for case_id)
    op.create_foreign_key(
        'fk_sampling_sites_case_id',
        'sampling_sites',
        'cases',
        ['case_id'],
        ['id']
    )
    
    # Create candidate_zones table
    op.create_table(
        'candidate_zones',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('root_hyriv_id', sa.Integer(), nullable=False),
        sa.Column('reach_ids', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('validation_status', sa.String(length=50), nullable=False),
        sa.Column('meta', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create evidence_items table
    op.create_table(
        'evidence_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('evidence_type', sa.String(length=100), nullable=False),
        sa.Column('source', sa.String(length=200), nullable=False),
        sa.Column('value', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('observed_at', sa.DateTime(), nullable=True),
        sa.Column('quality', sa.String(length=50), nullable=True),
        sa.Column('provenance', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create sampling_decisions table
    op.create_table(
        'sampling_decisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('case_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('recommended_site_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create decision_traces table
    op.create_table(
        'decision_traces',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, primary_key=True),
        sa.Column('decision_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('evidence_used', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('rules_applied', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('hydrology_checks', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('assumptions', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('limitations', postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['decision_id'], ['sampling_decisions.id'], ),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('decision_traces')
    op.drop_table('sampling_decisions')
    op.drop_table('evidence_items')
    op.drop_table('candidate_zones')
    
    # Drop foreign key from sampling_sites to cases before dropping cases
    op.drop_constraint('fk_sampling_sites_case_id', 'sampling_sites', type_='foreignkey')
    
    op.drop_table('cases')
    op.drop_table('sampling_sites')
