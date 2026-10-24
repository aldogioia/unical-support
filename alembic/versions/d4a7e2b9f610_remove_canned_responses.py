"""Remove canned responses; keep delivery language and transparency note per email.

Revision ID: d4a7e2b9f610
Revises: c8f4a1e6d203
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = 'd4a7e2b9f610'
down_revision = 'c8f4a1e6d203'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('emails', sa.Column('response_language', sa.String(16), nullable=True))
    op.add_column('emails', sa.Column('ai_disclaimer', sa.Text(), nullable=True))
    op.drop_table('template_category')
    op.drop_table('templates')
    postgresql.ENUM(name='templatestatus').drop(op.get_bind(), checkfirst=True)


def downgrade():
    status = postgresql.ENUM('ACTIVE', 'PENDING_APPROVAL', 'REJECTED', name='templatestatus', create_type=False)
    status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        'templates',
        sa.Column('id', sa.UUID(), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('subject_template', sa.String(255), nullable=True),
        sa.Column('body_template', sa.Text(), nullable=False),
        sa.Column('status', status, nullable=False),
        sa.Column('usage_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.String(36), nullable=False),
        sa.Column('last_updated_by', sa.String(36), nullable=False),
    )
    op.create_index('ix_templates_id', 'templates', ['id'])
    op.create_table(
        'template_category',
        sa.Column('template_id', sa.UUID(), sa.ForeignKey('templates.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('category_id', sa.UUID(), sa.ForeignKey('categories.id', ondelete='CASCADE'), primary_key=True),
    )
    op.drop_column('emails', 'ai_disclaimer')
    op.drop_column('emails', 'response_language')
