"""kb entry async fields: data_type, lang_hint, execution_id, status"""
from alembic import op
import sqlalchemy as sa

revision = "005_kb_entry_async_fields"
down_revision = "004_status_events_indexes"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("knowledge_entries", sa.Column("data_type", sa.String(length=32), nullable=False, server_default="document"))
    op.add_column("knowledge_entries", sa.Column("lang_hint", sa.String(length=16), nullable=False, server_default="ru"))
    op.add_column("knowledge_entries", sa.Column("execution_id", sa.String(length=64), nullable=True))
    op.add_column("knowledge_entries", sa.Column("status", sa.String(length=24), nullable=False, server_default="in_progress"))
    op.create_index("ix_ke_execution_id", "knowledge_entries", ["execution_id"])
    # external_entry_id index already exists in prior migration; keep it.

def downgrade():
    op.drop_index("ix_ke_execution_id", table_name="knowledge_entries")
    op.drop_column("knowledge_entries", "status")
    op.drop_column("knowledge_entries", "execution_id")
    op.drop_column("knowledge_entries", "lang_hint")
    op.drop_column("knowledge_entries", "data_type")
