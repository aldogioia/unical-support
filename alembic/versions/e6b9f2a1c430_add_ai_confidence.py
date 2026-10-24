"""Store optional retrieval confidence for new AI drafts.

Revision ID: e6b9f2a1c430
Revises: d4a7e2b9f610
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6b9f2a1c430'
down_revision = 'd4a7e2b9f610'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('emails', sa.Column('ai_confidence', sa.Float(), nullable=True))
    op.create_check_constraint('ck_emails_ai_confidence_range', 'emails', 'ai_confidence >= 0 AND ai_confidence <= 1')


def downgrade():
    op.drop_constraint('ck_emails_ai_confidence_range', 'emails', type_='check')
    op.drop_column('emails', 'ai_confidence')
