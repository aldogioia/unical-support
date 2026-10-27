"""Arrival ordering, optimistic drafts and fenced AI processing.

Revision ID: a71d9c4e2f60
Revises: f3a6c8e1b245
"""
from alembic import op
import sqlalchemy as sa

revision = 'a71d9c4e2f60'
down_revision = 'f3a6c8e1b245'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('emails', sa.Column('received_at', sa.DateTime(timezone=True), nullable=True))
    op.execute('UPDATE emails SET received_at = created_at')
    op.alter_column('emails', 'received_at', nullable=False, server_default=sa.func.now())
    op.create_index('ix_emails_received_id', 'emails', ['received_at', 'id'])
    for column in ['draft_revision', 'processing_generation']:
        op.add_column('emails', sa.Column(column, sa.Integer(), nullable=False, server_default='0'))
    op.add_column('emails', sa.Column('manually_edited', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Conservatively protect existing operator-owned answers, including delivery failures.
    op.execute("UPDATE emails SET manually_edited = true WHERE generated_draft IS NOT NULL AND last_updated_by <> 'System'")
    op.add_column('emails', sa.Column('processing_token', sa.String(36), nullable=True))
    op.add_column('emails', sa.Column('processing_started_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('emails', sa.Column('failure_stage', sa.String(16), nullable=True))


def downgrade():
    for column in ['failure_stage', 'processing_started_at', 'processing_token', 'manually_edited', 'processing_generation', 'draft_revision']:
        op.drop_column('emails', column)
    op.drop_index('ix_emails_received_id', table_name='emails')
    op.drop_column('emails', 'received_at')
