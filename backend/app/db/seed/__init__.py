"""
Run with: docker compose exec api python -m app.db.seed
Idempotent — safe to run multiple times.
Creates: 3 plans, N customers, N subscriptions (N from settings)
"""

import asyncio
import random
from faker import Faker
from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.db.models.seed.plan import Plan
from app.db.models.seed.customer import Customer
from app.db.models.seed.subscription import Subscription
from app.core.config import get_settings

fake = Faker()
settings = get_settings()

PLANS = [
    {"name": "Starter", "price_monthly": 29.00, "price_yearly": 290.00, "max_seats": 3},
    {"name": "Pro", "price_monthly": 99.00, "price_yearly": 990.00, "max_seats": 15},
    {
        "name": "Enterprise",
        "price_monthly": 349.00,
        "price_yearly": 3490.00,
        "max_seats": 999,
    },
]
REGIONS = ["EMEA", "AMER", "APAC"]
STATUSES = [
    "active",
    "active",
    "active",
    "cancelled",
    "trialing",
    "past_due",
]  # weighted
BILLING = ["monthly", "monthly", "yearly"]  # weighted toward monthly


async def seed():
    async with AsyncSessionLocal() as db:
        # 1. Create plans
        plan_map = {}
        for plan_data in PLANS:
            existing_plan = await db.execute(
                select(Plan).where(Plan.name == plan_data["name"])
            )
            if existing_plan.scalar_one_or_none() is not None:
                continue
            plan = Plan(**plan_data)
            db.add(plan)
            await db.flush()
            print(f"Created plan: {plan.name}")
            plan_map[plan.name] = plan

        # 2. Create customers
        existing_count = await db.execute(select(Customer))
        customers = existing_count.scalars().all()
        if len(customers) < settings.seed_customers:
            to_create = settings.seed_customers - len(customers)
            print(f"Creating {to_create} customers...")
            for _ in range(to_create):
                customer = Customer(
                    company_name=fake.company(),
                    email=fake.unique.company_email(),
                    country=fake.country(),
                    region=random.choice(REGIONS),
                    industry=fake.bs().split(" ")[-1].capitalize(),
                )
                db.add(customer)
            await db.flush()
            customers = (await db.execute(select(Customer))).scalars().all()

        # 3. Create subscriptions
        existing_count = await db.execute(select(Subscription))
        subscriptions = existing_count.scalars().all()
        if len(subscriptions) < settings.seed_subscriptions:
            to_create = settings.seed_subscriptions - len(subscriptions)
            print(f"Creating {to_create} subscriptions...")
            plans = list(plan_map.values())
            for _ in range(to_create):
                customer = random.choice(customers)
                plan = random.choice(plans)
                billing = random.choice(BILLING)
                seats = random.randint(1, min(plan.max_seats, 20))
                mrr = (
                    plan.price_monthly * seats
                    if billing == "monthly"
                    else (plan.price_yearly * seats / 12)
                )
                status = random.choice(STATUSES)
                subscription = Subscription(
                    customer_id=customer.id,
                    plan_id=plan.id,
                    status=status,
                    billing_cycle=billing,
                    seats=seats,
                    mrr=round(mrr, 2),
                    started_at=fake.date_between(start_date="-1y", end_date="now"),
                )
                db.add(subscription)
            await db.commit()
            print("Seed completed.")


if __name__ == "__main__":
    print("Seeding database...")
    asyncio.run(seed())
