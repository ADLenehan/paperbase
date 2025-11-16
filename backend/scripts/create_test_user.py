"""
Create or update test admin user with known password.

This script creates a test admin user for development/testing:
- Email: default@paperbase.local
- Password: admin
- Role: Admin (full access)

Usage:
    python scripts/create_test_user.py
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy.orm import Session
from app.core.database import SessionLocal, engine
from app.core.auth import hash_password
from app.models.settings import User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_or_update_test_user():
    """Create or update the test admin user."""
    db = SessionLocal()

    try:
        # Check if default user exists
        user = db.query(User).filter(User.email == "default@paperbase.local").first()

        if user:
            logger.info(f"Found existing user: {user.email}")

            # Update password
            user.hashed_password = hash_password("admin")
            user.is_admin = True
            user.is_active = True
            user.email_verified = True

            db.commit()
            logger.info("✓ Updated password for default@paperbase.local")
        else:
            logger.info("Creating new default admin user...")

            user = User(
                email="default@paperbase.local",
                name="Default Admin",
                hashed_password=hash_password("admin"),
                is_admin=True,
                is_active=True,
                email_verified=True,
                auth_provider="password"
            )

            db.add(user)
            db.commit()
            logger.info("✓ Created default@paperbase.local")

        logger.info("")
        logger.info("=" * 60)
        logger.info("Test User Credentials:")
        logger.info("=" * 60)
        logger.info(f"Email:    {user.email}")
        logger.info(f"Password: admin")
        logger.info(f"Is Admin: {user.is_admin}")
        logger.info(f"User ID:  {user.id}")
        logger.info("=" * 60)
        logger.info("")
        logger.info("You can now log in at: http://localhost:5173/login")
        logger.info("Or use the dev bypass button to skip login entirely.")

    except Exception as e:
        logger.error(f"Error creating test user: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    create_or_update_test_user()
