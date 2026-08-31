"""One-off fix for xx4 VIEWER Entra SSO 500 on Non-Prod.

Run inside the API pod (Jump VM):

  kubectl cp apps/api/scripts/fix_xx4_entra_user.py \\
    quanthire-nonprod/$(kubectl get pod -n quanthire-nonprod \\
    -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}'):/tmp/fix_xx4.py

  kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- python /tmp/fix_xx4.py
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.database import engine

SQL_ADD_VIEWER_ENUM = """
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

SQL_DELETE_XX4 = """
DELETE FROM users WHERE lower(email) = lower('xx4@malomatia.com');
"""


async def main() -> None:
    async with engine.begin() as conn:
        await conn.execute(text(SQL_ADD_VIEWER_ENUM))
        result = await conn.execute(text(SQL_DELETE_XX4))
        print("viewer enum check: OK")
        print("deleted xx4 rows:", result.rowcount)


if __name__ == "__main__":
    asyncio.run(main())
