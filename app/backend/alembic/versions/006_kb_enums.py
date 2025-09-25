"""Create DB ENUMs for KB fields and convert columns"""
from alembic import op
import sqlalchemy as sa

revision = "006_kb_enums"
down_revision = "005_kb_entry_async_fields"
branch_labels = None
depends_on = None

def upgrade():
    # Create enum types if missing
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'kb_data_type') THEN
            CREATE TYPE kb_data_type AS ENUM ('document','video');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'kb_entry_status') THEN
            CREATE TYPE kb_entry_status AS ENUM ('in_progress','done','timeout','failed');
        END IF;
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'kb_lang_hint') THEN
            CREATE TYPE kb_lang_hint AS ENUM (
                'ru','en','uk','tr','de','fr','es','it','pt','pl','kk','uz','az','ka','ro','nl',
                'sv','no','da','fi','cs','sk','bg','sr','hr','sl','et','lt','lv','el','he',
                'ar','fa','hi','ur','bn','ta','te','ml','id','ms','th','vi','zh','ja','ko'
            );
        END IF;
    END $$;
    """)

    # Drop defaults temporarily to change types safely
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN data_type DROP DEFAULT")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN lang_hint DROP DEFAULT")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN status DROP DEFAULT")

    # Convert varchar -> enum with USING casts
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN data_type TYPE kb_data_type USING data_type::kb_data_type")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN lang_hint TYPE kb_lang_hint USING lang_hint::kb_lang_hint")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN status TYPE kb_entry_status USING status::kb_entry_status")

    # Re-set defaults
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN data_type SET DEFAULT 'document'")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN lang_hint SET DEFAULT 'ru'")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN status SET DEFAULT 'in_progress'")

def downgrade():
    # Convert enum -> varchar to drop types
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN data_type TYPE varchar USING data_type::text")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN lang_hint TYPE varchar USING lang_hint::text")
    op.execute("ALTER TABLE knowledge_entries ALTER COLUMN status TYPE varchar USING status::text")

    # Drop enum types
    op.execute("DROP TYPE IF EXISTS kb_data_type")
    op.execute("DROP TYPE IF EXISTS kb_entry_status")
    op.execute("DROP TYPE IF EXISTS kb_lang_hint")
