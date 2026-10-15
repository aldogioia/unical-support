"""add document reference_url

Revision ID: b7e2f6c8d901
Revises: a3c9d2f4b7e1
Create Date: 2026-10-14 20:59:25.517194

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7e2f6c8d901'
down_revision = 'a3c9d2f4b7e1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('reference_url', sa.String(length=2048), nullable=True))
    # Preserve citation links supplied by legacy clients.
    op.execute("UPDATE documents SET reference_url = link WHERE link ~* '^https?://[^[:space:]]+$'")
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT to_regclass('public.langchain_pg_embedding') IS NOT NULL")).scalar():
        op.execute("""
            UPDATE langchain_pg_embedding e
            SET cmetadata = COALESCE(e.cmetadata, '{}'::jsonb) || jsonb_build_object(
                'reference_url', d.reference_url, 'source_name', d.filename
            )
            FROM documents d
            WHERE e.cmetadata->>'document_id' = d.id::text
        """)


def downgrade():
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT to_regclass('public.langchain_pg_embedding') IS NOT NULL")).scalar():
        op.execute("UPDATE langchain_pg_embedding SET cmetadata = cmetadata - 'reference_url' - 'source_name'")
    op.drop_column('documents', 'reference_url')
