#!/usr/bin/env python
"""
Create a system administrator user.

System admins have the 'system_admin' role and can access platform-wide
admin endpoints (view all tenants, all jobs, etc.) via /api/v1/admin/*.

Usage:
    docker compose exec api uv run python scripts/create_system_admin.py

This will prompt for email and password, then create a system_admin user
in a special system tenant.
"""
import asyncio
import sys
import getpass
from sqlalchemy import select
from app.db.base import AsyncSessionLocal
from app.db.models.user import User
from app.db.models.tenant import Tenant
from app.core.security import hash_password
# from app.core.utils import create_slug


async def create_system_admin():
    """Create a system administrator user interactively."""
    print("=" * 60)
    print("Create System Administrator")
    print("=" * 60)
    print()
    print("System admins can access platform-wide admin endpoints:")
    print("  - View all tenants")
    print("  - View all jobs across tenants")
    print("  - Manage DLQ entries for all tenants")
    print()

    # Get email
    while True:
        email = input("Email address: ").strip()
        if "@" in email and "." in email:
            break
        print("❌ Invalid email format. Please try again.")

    # Get password
    while True:
        password = getpass.getpass("Password (min 8 characters): ")
        if len(password) >= 8:
            password_confirm = getpass.getpass("Confirm password: ")
            if password == password_confirm:
                break
            print("❌ Passwords do not match. Please try again.")
        else:
            print("❌ Password must be at least 8 characters.")

    print()
    print("Creating system administrator...")

    async with AsyncSessionLocal() as db:
        try:
            # Check if email already exists
            result = await db.execute(select(User).where(User.email == email))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                print(f"❌ Error: User with email '{email}' already exists.")
                print(f"   Existing user has role: {existing_user.role}")
                if existing_user.role == "system_admin":
                    print("   This user is already a system admin.")
                else:
                    print("   To upgrade this user to system_admin, update the database directly:")
                    print(f"   UPDATE users SET role='system_admin' WHERE id='{existing_user.id}';")
                sys.exit(1)

            # Create or get the system tenant
            result = await db.execute(
                select(Tenant).where(Tenant.slug == "system")
            )
            system_tenant = result.scalar_one_or_none()

            if not system_tenant:
                system_tenant = Tenant(
                    name="System",
                    slug="system",
                    is_active=True
                )
                db.add(system_tenant)
                await db.flush()
                print(f"✓ Created system tenant (id: {system_tenant.id})")

            # Create system admin user
            system_admin = User(
                tenant_id=system_tenant.id,
                email=email,
                hashed_password=hash_password(password),
                role="system_admin",  # ✅ System administrator role
                is_active=True
            )
            db.add(system_admin)
            await db.commit()

            print()
            print("✅ System administrator created successfully!")
            print()
            print(f"   Email:     {email}")
            print("   Role:      system_admin")
            print(f"   Tenant:    System (id: {system_tenant.id})")
            print(f"   User ID:   {system_admin.id}")
            print()
            print("This user can now:")
            print("  - Access /api/v1/admin/* endpoints")
            print("  - View all tenants via GET /api/v1/admin/tenants")
            print("  - View all jobs via GET /api/v1/admin/jobs")
            print("  - Manage DLQ entries across all tenants")
            print()
            print("To log in:")
            print("  POST /api/v1/auth/token")
            print(f"  Body: {{'email': '{email}', 'password': '***'}}")
            print()

        except Exception as e:
            await db.rollback()
            print(f"❌ Error creating system admin: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(create_system_admin())
