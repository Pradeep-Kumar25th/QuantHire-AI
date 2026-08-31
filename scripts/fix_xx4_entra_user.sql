-- Fix xx4 VIEWER SSO: entra/callback 500 "while saving your account"
-- Run on Azure Postgres Non-Prod (psql or Azure portal) with approval.

-- 1) If PostgreSQL uses a native enum type missing 'viewer', add it:
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

-- 2) Reset broken xx4 row (clears bad org_id / role); next SSO login recreates it:
DELETE FROM users WHERE lower(email) = lower('xx4@malomatia.com');

-- Alternative to DELETE — normalize in place:
-- UPDATE users
-- SET role = 'viewer', org_id = NULL, is_active = true, is_verified = true, updated_at = NOW()
-- WHERE lower(email) = lower('xx4@malomatia.com');
