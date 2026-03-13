"""
Run with: docker compose exec api uv run python -m app.db.seed
Idempotent — safe to run multiple times.
Creates: 3 plans, 500 customers, 1200 subscriptions (configurable via settings)
"""
import asyncio
from app.db.seed import seed

if __name__ == "__main__":
    print("Seeding database...")
    asyncio.run(seed())
    print("Seed completed successfully!")
