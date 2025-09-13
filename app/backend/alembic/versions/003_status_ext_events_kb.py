"""extend instance_status; add status events & knowledge base"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "003_status_ext_events_kb"
down_revision = "002_add_instance_id"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # extend enum
    for val in ["provisioning","inactive","updating","deleting","error","unknown"]:
        op.execute(f"ALTER TYPE instance_status ADD VALUE IF NOT EXISTS '{val}'")

    # status events
    op.create_table(
        "instance_status_events",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instance_id", sa.BigInteger(), sa.ForeignKey("user_bot_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(length=50), nullable=True),
        sa.Column("to_status", sa.String(length=50), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ise_instance_id", "instance_status_events", ["instance_id"])

    # knowledge base
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("instance_id", sa.BigInteger(), sa.ForeignKey("user_bot_instances.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_kb_instance_id", "knowledge_bases", ["instance_id"])

    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("kb_id", sa.BigInteger(), sa.ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("external_entry_id", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )
    op.create_index("ix_ke_kb_id", "knowledge_entries", ["kb_id"])
    op.create_index("ix_ke_external_entry_id", "knowledge_entries", ["external_entry_id"])
    op.create_unique_constraint("uq_kb_external_entry", "knowledge_entries", ["kb_id","external_entry_id"])

def downgrade() -> None:
    op.drop_constraint("uq_kb_external_entry", "knowledge_entries", type_="unique")
    op.drop_index("ix_ke_external_entry_id", table_name="knowledge_entries")
    op.drop_index("ix_ke_kb_id", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")

    op.drop_index("ix_kb_instance_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")

    op.drop_index("ix_ise_instance_id", table_name="instance_status_events")
    op.drop_table("instance_status_events")
    # do not shrink enums in downgrade
