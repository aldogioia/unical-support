"""Documents: multi-category (many-to-many via document_category)

Revision ID: a3c9d2f4b7e1
Revises: e199718ba57d
Create Date: 2026-10-05 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a3c9d2f4b7e1'
down_revision = 'e199718ba57d'
branch_labels = None
depends_on = None


def _embedding_table_exists(bind) -> bool:
    return bind.execute(sa.text("SELECT to_regclass('public.langchain_pg_embedding') IS NOT NULL")).scalar()


def upgrade():
    # 1. Tabella di associazione
    op.create_table('document_category',
    sa.Column('document_id', sa.UUID(), nullable=False),
    sa.Column('category_id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('document_id', 'category_id')
    )

    # 2. Migrazione dati: la categoria singola esistente diventa la prima associazione
    op.execute(
        "INSERT INTO document_category (document_id, category_id) "
        "SELECT id, category_id FROM documents WHERE category_id IS NOT NULL"
    )

    # 3. Allineamento metadati dei chunk nel Vector Store: 'category' (stringa) -> 'categories' (lista)
    bind = op.get_bind()
    if _embedding_table_exists(bind):
        op.execute(
            """
            UPDATE langchain_pg_embedding e
            SET cmetadata = (e.cmetadata - 'category') || jsonb_build_object(
                'categories',
                COALESCE(
                    (SELECT jsonb_agg(c.name ORDER BY c.name)
                     FROM document_category dc
                     JOIN categories c ON c.id = dc.category_id
                     WHERE dc.document_id::text = e.cmetadata->>'document_id'),
                    '[]'::jsonb
                )
            )
            WHERE e.cmetadata->>'document_id' IS NOT NULL
            """
        )

    # 4. Rimozione della vecchia colonna (e relativa FK)
    with op.batch_alter_table('documents') as batch_op:
        batch_op.drop_column('category_id')


def downgrade():
    op.add_column('documents', sa.Column('category_id', sa.UUID(), nullable=True))
    op.create_foreign_key(
        'documents_category_id_fkey', 'documents', 'categories',
        ['category_id'], ['id'], ondelete='CASCADE'
    )

    # Ripristino best-effort: si mantiene una sola categoria per documento (la prima per nome)
    op.execute(
        """
        UPDATE documents d
        SET category_id = sub.category_id
        FROM (
            SELECT DISTINCT ON (dc.document_id) dc.document_id, dc.category_id
            FROM document_category dc
            JOIN categories c ON c.id = dc.category_id
            ORDER BY dc.document_id, c.name
        ) sub
        WHERE d.id = sub.document_id
        """
    )

    bind = op.get_bind()
    if _embedding_table_exists(bind):
        op.execute(
            """
            UPDATE langchain_pg_embedding e
            SET cmetadata = (e.cmetadata - 'categories') || jsonb_build_object(
                'category',
                COALESCE(
                    (SELECT c.name FROM documents d JOIN categories c ON c.id = d.category_id
                     WHERE d.id::text = e.cmetadata->>'document_id'),
                    'Generale'
                )
            )
            WHERE e.cmetadata->>'document_id' IS NOT NULL
            """
        )

    op.drop_table('document_category')
