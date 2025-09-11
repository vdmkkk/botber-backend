"""add instance_id to user_bot_instances"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_add_instance_id_to_user_bot_instances"
down_revision = "001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1) add column nullable so we can backfill
    op.add_column(
        "user_bot_instances",
        sa.Column("instance_id", sa.String(length=100), nullable=True),
    )
    # 2) backfill existing rows with deterministic legacy ids
    op.execute("UPDATE user_bot_instances SET instance_id = 'legacy-' || id::text WHERE instance_id IS NULL")
    # 3) set NOT NULL
    op.alter_column("user_bot_instances", "instance_id", nullable=False)
    # 4) add unique + index
    op.create_unique_constraint("uq_user_bot_instances_instance_id", "user_bot_instances", ["instance_id"])
    op.create_index("ix_user_bot_instances_instance_id", "user_bot_instances", ["instance_id"])

def downgrade() -> None:
    op.drop_index("ix_user_bot_instances_instance_id", table_name="user_bot_instances")
    op.drop_constraint("uq_user_bot_instances_instance_id", "user_bot_instances", type_="unique")
    op.drop_column("user_bot_instances", "instance_id")
