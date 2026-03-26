#!/usr/bin/env python3
"""
Set a user's role to admin
Usage: docker compose exec api uv run python scripts/set_admin_role.py <email>
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.db.models.user import User


async def set_admin_role(email: str):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user is None:
            print(f"❌ User '{email}' not found")
            return

        if user.role == "admin":
            print(f"✅ User '{email}' is already an admin")
            return

        user.role = "admin"
        await db.commit()
        print(f"✅ User '{email}' role updated to 'admin'")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/set_admin_role.py <email>")
        sys.exit(1)

    email = sys.argv[1]
    asyncio.run(set_admin_role(email))
