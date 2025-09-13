"""indexes for status events"""
from alembic import op
import sqlalchemy as sa

revision = "004_status_events_indexes"
down_revision = "003_status_ext_events_kb"
branch_labels = None
depends_on = None

def upgrade():
    op.create_index("ix_ise_instance_changed", "instance_status_events", ["instance_id", "changed_at"])
    op.create_index("ix_ise_changed_at", "instance_status_events", ["changed_at"])

def downgrade():
    op.drop_index("ix_ise_changed_at", table_name="instance_status_events")
    op.drop_index("ix_ise_instance_changed", table_name="instance_status_events")
