"""Ensure PostgreSQL userrole enum includes viewer (fixes xx4 Entra SSO 500).

Revision ID: add_viewer_user_role_enum
"""

from alembic import op

revision = "add_viewer_user_role_enum"
down_revision = "add_document_chunks_pgvector"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # No-op when role is stored as VARCHAR. Safe when native enum exists but lacks viewer.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userrole') THEN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_enum e
                    JOIN pg_type t ON e.enumtypid = t.oid
                    WHERE t.typname = 'userrole' AND e.enumlabel = 'viewer'
                ) THEN
                    ALTER TYPE userrole ADD VALUE 'viewer';
                END IF;
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # PostgreSQL cannot remove enum values safely; leave viewer in place.
    pass
