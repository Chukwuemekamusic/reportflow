#!/usr/bin/env python3
"""
Check user role in the database
Usage: docker compose exec api uv run python scripts/check_user_role.py <email>
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.db.models.user import User


async def check_user_role(email: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"❌ User '{email}' not found")
            return

        print(f"✅ User found:")
        print(f"   Email:     {user.email}")
        print(f"   Role:      {user.role}")
        print(f"   Tenant ID: {user.tenant_id}")
        print(f"   Active:    {user.is_active}")
        print(f"   Created:   {user.created_at}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/check_user_role.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    asyncio.run(check_user_role(email))
