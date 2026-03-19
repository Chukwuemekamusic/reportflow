#!/usr/bin/env python3
"""Debug DLQ query"""
import asyncio
from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.db.models.dead_letter import DeadLetterQueue


async def debug_dlq():
    async with AsyncSessionLocal() as db:
        # Test the exact query from the endpoint
        result = await db.execute(
            select(DeadLetterQueue)
            .where(DeadLetterQueue.resolved == False)
            .order_by(DeadLetterQueue.created_at.desc())
            .limit(50)
            .offset(0)
        )
        entries = result.scalars().all()

        print(f"Found {len(entries)} entries")
        for entry in entries:
            print(f"  - {entry.job_id} | tenant: {entry.tenant_id} | resolved: {entry.resolved}")


if __name__ == "__main__":
    asyncio.run(debug_dlq())
