#!/usr/bin/env python3
"""Pre-provision Malomatia HR recruiters with RECRUITER role (same as xx1@malomatia.com).

Entra SSO also upserts users on first Microsoft login; run this script only when you
want DB records ready before first sign-in or to fix role mismatches after login.

Usage (local, DATABASE_URL set):
  python apps/api/scripts/provision_hr_recruiters.py

Usage (NPD API pod):
  kubectl cp apps/api/scripts/provision_hr_recruiters.py \\
    quanthire-nonprod/$(kubectl get pod -n quanthire-nonprod \\
    -l app.kubernetes.io/component=api -o jsonpath='{.items[0].metadata.name}'):/tmp/provision_hr_recruiters.py
  kubectl exec deploy/quanthire-nonprod-api -n quanthire-nonprod -- python /tmp/provision_hr_recruiters.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from dotenv import load_dotenv

load_dotenv(API_ROOT / ".env")
_repo_root = API_ROOT.parent.parent
if (_repo_root / "apps" / "api").resolve() == API_ROOT.resolve():
    load_dotenv(_repo_root / ".env")

from app.core.role_labels import HR_RECRUITER_EMAILS

# Same Entra app role / PostgreSQL label as xx1@malomatia.com (RECRUITER).
HR_RECRUITERS: list[tuple[str, str]] = [
    ("vbhushan@malomatia.com", "Vaibhav Bharat Bhushan"),
    ("rcambell@malomatia.com", "Rohan Cambell"),
    ("kpole@malomatia.com", "Ketaki Pole"),
    ("rxavier@malomatia.com", "Romin Xavier"),
    ("nsahare@malomatia.com", "Nisha Sahare"),
    ("mvismonte@malomatia.com", "Melanie Carlos Vismonte"),
    ("pdudhnale@malomatia.com", "Pradeep Dudhnale"),
    ("rgirle@malomatia.com", "Richard Duncan Girle"),
]

assert tuple(email for email, _ in HR_RECRUITERS) == HR_RECRUITER_EMAILS


async def main() -> None:
    from app.api.v1.auth import _upsert_entra_user
    from app.database import get_session, init_db
    from app.models.users import UserRole

    await init_db()

    async for session in get_session():
        for email, name in HR_RECRUITERS:
            user = await _upsert_entra_user(
                session,
                email=email,
                name=name,
                role=UserRole.RECRUITER,
            )
            print(f"OK  {user.email}  role=RECRUITER  name={user.name}")
        print(f"\nProvisioned {len(HR_RECRUITERS)} recruiters (same role as xx1@malomatia.com).")
        return

    raise RuntimeError("Database session unavailable — set DATABASE_URL.")


if __name__ == "__main__":
    asyncio.run(main())
