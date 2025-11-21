#!/usr/bin/env python3
"""Create admin user for testing"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.core.auth import hash_password
from app.models.settings import User

def create_admin():
    db = SessionLocal()

    try:
        # Delete existing user
        db.query(User).filter(User.email == "admin@paperbase.dev").delete()
        db.commit()

        # Create new admin user
        admin = User(
            org_id=1,  # Default organization
            email="admin@paperbase.dev",
            name="Admin User",
            hashed_password=hash_password("admin"),
            auth_provider="password",
            organization_role="owner",
            is_admin=True,
            is_active=True,
            email_verified=True,
            onboarding_completed=True
        )

        db.add(admin)
        db.commit()
        db.refresh(admin)

        print("=" * 60)
        print("✅ Admin user created successfully!")
        print("=" * 60)
        print(f"Email:    {admin.email}")
        print(f"Password: admin")
        print(f"ID:       {admin.id}")
        print(f"Is Admin: {admin.is_admin}")
        print("=" * 60)
        print("\nYou can now login at: http://localhost:5173/login")

    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        raise
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
