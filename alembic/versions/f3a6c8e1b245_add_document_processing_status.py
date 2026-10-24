"""Track normalization/review status for uploaded documents.

Revision ID: f3a6c8e1b245
Revises: e6b9f2a1c430
"""
from alembic import op
import sqlalchemy as sa

revision = 'f3a6c8e1b245'
down_revision = 'e6b9f2a1c430'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('processing_status', sa.String(20), nullable=False, server_default='pending'))
    op.add_column('documents', sa.Column('review_notes', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('documents', 'review_notes')
    op.drop_column('documents', 'processing_status')
