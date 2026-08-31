#!/usr/bin/env python3
"""Create an initial HR test user for basic-auth login (Non-Prod v1)."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

# apps/api locally, /app in the production container (see Dockerfile.backend)
API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from dotenv import load_dotenv

load_dotenv(API_ROOT / ".env")
_repo_root = API_ROOT.parent.parent
if (_repo_root / "apps" / "api").resolve() == API_ROOT.resolve():
    load_dotenv(_repo_root / ".env")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create QuantHire basic-auth test user")
    parser.add_argument("--email", default=os.getenv("TEST_USER_EMAIL", "hr.test@malomatia.com"))
    parser.add_argument("--name", default=os.getenv("TEST_USER_NAME", "HR Test User"))
    parser.add_argument("--password", default=os.getenv("TEST_USER_PASSWORD", "ChangeMe123!"))
    parser.add_argument("--role", default="recruiter", choices=["admin", "recruiter", "hiring_manager"])
    args = parser.parse_args()

    from app.database import init_db, get_session
    from app.core.security import get_password_hash
    from app.models.users import User, UserRole
    from sqlalchemy import select

    await init_db()

    async for session in get_session():
        result = await session.execute(select(User).where(User.email == args.email))
        existing = result.scalar_one_or_none()
        if existing:
            existing.hashed_password = get_password_hash(args.password)
            existing.is_active = True
            existing.role = UserRole(args.role)
            existing.name = args.name
            await session.commit()
            print(f"Updated existing user: {args.email} (role={args.role})")
            return

        user = User(
            email=args.email,
            name=args.name,
            role=UserRole(args.role),
            hashed_password=get_password_hash(args.password),
            is_active=True,
            is_verified=True,
        )
        session.add(user)
        await session.commit()
        print(f"Created user: {args.email} (role={args.role})")
        return

    raise RuntimeError("Database session unavailable — set DATABASE_URL and ensure Postgres is reachable.")


if __name__ == "__main__":
    asyncio.run(main())
