"""Add normalized species and detection contexts; preserve legacy records."""
from alembic import op
import sqlalchemy as sa

revision='d4e93b7a2601'
down_revision='c9d42e8a710f'
branch_labels=None
depends_on=None
SCOPED=['sampling_sites','evidence_items','candidate_zones','sampling_decisions','investigation_runs',
        'follow_up_samples','hypothesis_states','generated_candidate_snapshots','context_executions']


def upgrade():
    op.create_table('target_species',sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('case_id',sa.UUID(),sa.ForeignKey('cases.id'),nullable=False),
        sa.Column('taxon',sa.String(200),nullable=False),
        sa.UniqueConstraint('case_id','taxon',name='uq_species_case_taxon'),
        sa.UniqueConstraint('id','case_id',name='uq_species_id_case'))
    op.create_index('ix_target_species_case_id','target_species',['case_id'])
    op.create_table('detection_contexts',sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('case_id',sa.UUID(),sa.ForeignKey('cases.id'),nullable=False),
        sa.Column('species_id',sa.UUID(),nullable=False),
        sa.Column('site_id',sa.UUID(),sa.ForeignKey('sampling_sites.id'),nullable=False),
        sa.Column('sampled_on',sa.Date(),nullable=False),sa.Column('event_label',sa.String(200),nullable=False),
        sa.Column('is_primary',sa.Boolean(),nullable=False),sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.ForeignKeyConstraint(['species_id','case_id'],['target_species.id','target_species.case_id']),
        sa.UniqueConstraint('id','case_id',name='uq_detection_context_id_case'),
        sa.UniqueConstraint('case_id','species_id','site_id','sampled_on','event_label',name='uq_detection_event'))
    op.create_index('ix_detection_contexts_case_id','detection_contexts',['case_id'])
    op.create_index('uq_primary_detection_context','detection_contexts',['case_id'],unique=True,
        postgresql_where=sa.text('is_primary = true'),sqlite_where=sa.text('is_primary = 1'))
    op.create_table('replicate_observations',sa.Column('id',sa.UUID(),primary_key=True),
        sa.Column('case_id',sa.UUID(),sa.ForeignKey('cases.id'),nullable=False),
        sa.Column('detection_context_id',sa.UUID(),nullable=False),
        sa.Column('evidence_id',sa.UUID(),sa.ForeignKey('evidence_items.id'),nullable=False),
        sa.Column('replicate_index',sa.Integer(),nullable=False),sa.Column('result',sa.String(20),nullable=False),
        sa.ForeignKeyConstraint(['detection_context_id','case_id'],['detection_contexts.id','detection_contexts.case_id']),
        sa.UniqueConstraint('evidence_id','replicate_index',name='uq_evidence_replicate'))
    op.create_index('ix_replicate_observations_detection_context_id','replicate_observations',['detection_context_id'])
    for table in SCOPED:
        op.add_column(table,sa.Column('detection_context_id',sa.UUID(),nullable=True))
        op.create_foreign_key(f'fk_{table}_detection_context',table,'detection_contexts',
                              ['detection_context_id','case_id'],['id','case_id'])
        op.create_index(f'ix_{table}_detection_context_id',table,['detection_context_id'])
    # Set-based PostgreSQL backfill also supports Alembic offline SQL export.
    op.execute("""INSERT INTO target_species (id,case_id,taxon)
        SELECT md5('freshwater-species:' || id::text)::uuid,id,target_taxon FROM cases""")
    op.execute("""INSERT INTO detection_contexts (id,case_id,species_id,site_id,sampled_on,event_label,is_primary,created_at)
        SELECT md5('freshwater-primary:' || id::text)::uuid,id,
        md5('freshwater-species:' || id::text)::uuid,detection_site_id,observation_date,
        'Legacy primary observation',true,created_at FROM cases""")
    for table in SCOPED:
        physical_filter = " AND source.site_type <> 'DETECTION_SITE'" if table == 'sampling_sites' else ""
        op.execute(f"""UPDATE {table} AS source SET detection_context_id = context.id
            FROM detection_contexts AS context WHERE source.case_id = context.case_id{physical_filter}""")
    op.execute("""INSERT INTO replicate_observations
        (id,case_id,detection_context_id,evidence_id,replicate_index,result)
        SELECT md5('freshwater-replicate:' || evidence.id::text || ':' || replicate.ordinality::text)::uuid,
            evidence.case_id,evidence.detection_context_id,evidence.id,replicate.ordinality,replicate.value
        FROM evidence_items AS evidence
        CROSS JOIN LATERAL jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(evidence.value->'replicate_results') = 'array'
            THEN evidence.value->'replicate_results' ELSE '[]'::jsonb END
        ) WITH ORDINALITY AS replicate(value,ordinality)
        WHERE evidence.evidence_type = 'edna_observation'
          AND NOT EXISTS (SELECT 1 FROM jsonb_array_elements_text(
            CASE WHEN jsonb_typeof(evidence.value->'replicate_results') = 'array'
            THEN evidence.value->'replicate_results' ELSE '[]'::jsonb END) AS result(value)
            WHERE result.value IS NULL OR result.value NOT IN ('Positive','Negative','Invalid'))""")


def downgrade():
    op.drop_table('replicate_observations')
    for table in reversed(SCOPED):
        op.drop_constraint(f'fk_{table}_detection_context',table,type_='foreignkey')
        op.drop_index(f'ix_{table}_detection_context_id',table_name=table)
        op.drop_column(table,'detection_context_id')
    op.drop_table('detection_contexts')
    op.drop_table('target_species')
