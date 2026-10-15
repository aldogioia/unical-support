"""Keep a single document citation link; remove web ingestion's legacy field.

Revision ID: c8f4a1e6d203
Revises: b7e2f6c8d901
"""
from alembic import op
import sqlalchemy as sa

revision = 'c8f4a1e6d203'
down_revision = 'b7e2f6c8d901'
branch_labels = None
depends_on = None


def upgrade():
    # Never overwrite the citation URL explicitly chosen by an operator.
    op.execute("""
        UPDATE documents SET reference_url = link
        WHERE (reference_url IS NULL OR btrim(reference_url) = '')
          AND link ~* '^https?://[^[:space:]]+$'
    """)
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT to_regclass('public.langchain_pg_embedding') IS NOT NULL")).scalar():
        op.execute("""
            UPDATE langchain_pg_embedding e
            SET cmetadata = COALESCE(e.cmetadata, '{}'::jsonb) || jsonb_build_object(
                'reference_url', d.reference_url, 'source_name', d.filename
            )
            FROM documents d WHERE e.cmetadata->>'document_id' = d.id::text
        """)
    op.drop_column('documents', 'link')


def downgrade():
    # Match the legacy column length. The full URL remains in reference_url.
    op.add_column('documents', sa.Column('link', sa.String(length=500), nullable=True))
    op.execute("UPDATE documents SET link = left(reference_url, 500)")
