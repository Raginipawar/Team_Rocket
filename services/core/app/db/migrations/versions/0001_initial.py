"""initial migration

Revision ID: 0001
Revises: 
Create Date: 2024-03-24 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2
from app.db.models import Base

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist;")
    
    # updated_at trigger function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)

    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'audit_log') THEN
                CREATE OR REPLACE RULE audit_no_update AS ON UPDATE TO audit_log DO INSTEAD NOTHING;
                CREATE OR REPLACE RULE audit_no_delete AS ON DELETE TO audit_log DO INSTEAD NOTHING;
            END IF;
        END $$;
    """)

def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column CASCADE;")
    op.execute("DROP EXTENSION IF EXISTS btree_gist;")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm;")
    op.execute("DROP EXTENSION IF EXISTS postgis;")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto;")
