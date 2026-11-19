"""Persist retrieved source snapshots with email drafts.

Revision ID: c2d8e4f6a901
Revises: a71d9c4e2f60
"""
from alembic import op
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB

revision = 'c2d8e4f6a901'
down_revision = 'a71d9c4e2f60'
branch_labels = None
depends_on = None


def upgrade():
    # NULL means no historical retrieval record; [] means a recorded empty search.
    op.add_column('emails', Column('retrieved_sources', JSONB(), nullable=True))


def downgrade():
    op.drop_column('emails', 'retrieved_sources')
