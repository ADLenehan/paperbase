"""
Database Migration: Add OAuth and Multi-Tenancy Support

This migration adds:
1. OAuth fields to User model (auth_provider, provider_user_id, provider_metadata)
2. Organization ownership (owner_id on Organization)
3. Organization membership fields (organization_role, onboarding_completed on User)
4. Multi-tenancy (organization_id on Document, Schema, PhysicalFile)
5. OrganizationInvite table

Run this migration to upgrade existing databases to support OAuth authentication
and multi-tenancy.

Usage:
    python migrations/add_oauth_and_organizations.py
"""

import sys
import os
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, DATABASE_URL
from app.models.settings import Organization, User, OrganizationInvite
from app.models.document import Document
from app.models.schema import Schema
from app.models.physical_file import PhysicalFile
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """
    Run the OAuth and multi-tenancy migration.

    Steps:
    1. Add new columns to existing tables
    2. Create OrganizationInvite table
    3. Create default organization
    4. Migrate existing data
    """
    logger.info("Starting OAuth and multi-tenancy migration...")

    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Step 1: Add columns using raw SQL (SQLite doesn't support DROP COLUMN)
        logger.info("Adding new columns...")

        with engine.connect() as conn:
            # Add OAuth fields to users table
            try:
                conn.execute('ALTER TABLE users ADD COLUMN auth_provider VARCHAR DEFAULT "password"')
                logger.info("✓ Added auth_provider to users")
            except Exception as e:
                logger.warning(f"auth_provider may already exist: {e}")

            try:
                conn.execute('ALTER TABLE users ADD COLUMN provider_user_id VARCHAR')
                logger.info("✓ Added provider_user_id to users")
            except Exception as e:
                logger.warning(f"provider_user_id may already exist: {e}")

            try:
                conn.execute('ALTER TABLE users ADD COLUMN provider_metadata TEXT')
                logger.info("✓ Added provider_metadata to users")
            except Exception as e:
                logger.warning(f"provider_metadata may already exist: {e}")

            try:
                conn.execute('ALTER TABLE users ADD COLUMN provider_linked_at DATETIME')
                logger.info("✓ Added provider_linked_at to users")
            except Exception as e:
                logger.warning(f"provider_linked_at may already exist: {e}")

            # Add organization membership fields to users table
            try:
                conn.execute('ALTER TABLE users ADD COLUMN organization_role VARCHAR')
                logger.info("✓ Added organization_role to users")
            except Exception as e:
                logger.warning(f"organization_role may already exist: {e}")

            try:
                conn.execute('ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0')
                logger.info("✓ Added onboarding_completed to users")
            except Exception as e:
                logger.warning(f"onboarding_completed may already exist: {e}")

            try:
                conn.execute('ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0')
                logger.info("✓ Added email_verified to users")
            except Exception as e:
                logger.warning(f"email_verified may already exist: {e}")

            # Add owner_id to organizations table
            try:
                conn.execute('ALTER TABLE organizations ADD COLUMN owner_id INTEGER REFERENCES users(id)')
                logger.info("✓ Added owner_id to organizations")
            except Exception as e:
                logger.warning(f"owner_id may already exist: {e}")

            # Add organization_id to documents table
            try:
                conn.execute('ALTER TABLE documents ADD COLUMN organization_id INTEGER REFERENCES organizations(id)')
                logger.info("✓ Added organization_id to documents")
            except Exception as e:
                logger.warning(f"organization_id may already exist in documents: {e}")

            # Add organization_id to schemas table
            try:
                conn.execute('ALTER TABLE schemas ADD COLUMN organization_id INTEGER REFERENCES organizations(id)')
                logger.info("✓ Added organization_id to schemas")
            except Exception as e:
                logger.warning(f"organization_id may already exist in schemas: {e}")

            # Add organization_id to physical_files table
            try:
                conn.execute('ALTER TABLE physical_files ADD COLUMN organization_id INTEGER REFERENCES organizations(id)')
                logger.info("✓ Added organization_id to physical_files")
            except Exception as e:
                logger.warning(f"organization_id may already exist in physical_files: {e}")

            conn.commit()

        # Step 2: Create OrganizationInvite table if it doesn't exist
        logger.info("Creating OrganizationInvite table...")
        Base.metadata.create_all(bind=engine, tables=[OrganizationInvite.__table__])
        logger.info("✓ OrganizationInvite table created")

        # Step 3: Create default organization if none exists
        logger.info("Checking for default organization...")
        default_org = session.query(Organization).filter(Organization.id == 1).first()

        if not default_org:
            logger.info("Creating default organization...")
            default_org = Organization(
                id=1,
                name="Default Organization",
                slug="default",
                is_active=True,
                created_at=datetime.utcnow()
            )
            session.add(default_org)
            session.commit()
            logger.info("✓ Default organization created")
        else:
            logger.info("✓ Default organization already exists")

        # Step 4: Migrate existing users
        logger.info("Migrating existing users...")
        users = session.query(User).all()

        for user in users:
            # Set default values for new fields
            if not user.auth_provider:
                user.auth_provider = "password"

            if user.org_id is None:
                user.org_id = 1  # Assign to default org

            if not user.organization_role:
                # First user becomes owner, others become members
                if user.id == 1:
                    user.organization_role = "owner"
                    default_org.owner_id = user.id
                else:
                    user.organization_role = "member"

            if not hasattr(user, 'onboarding_completed'):
                user.onboarding_completed = True

            if not hasattr(user, 'email_verified'):
                user.email_verified = True  # Assume existing users are verified

        session.commit()
        logger.info(f"✓ Migrated {len(users)} users")

        # Step 5: Migrate existing documents
        logger.info("Migrating existing documents...")
        documents = session.query(Document).filter(Document.organization_id == None).all()

        for doc in documents:
            doc.organization_id = 1  # Assign to default org

        session.commit()
        logger.info(f"✓ Migrated {len(documents)} documents")

        # Step 6: Migrate existing schemas
        logger.info("Migrating existing schemas...")
        schemas = session.query(Schema).filter(Schema.organization_id == None).all()

        for schema in schemas:
            schema.organization_id = 1  # Assign to default org

        session.commit()
        logger.info(f"✓ Migrated {len(schemas)} schemas")

        # Step 7: Migrate existing physical files
        logger.info("Migrating existing physical files...")
        files = session.query(PhysicalFile).filter(PhysicalFile.organization_id == None).all()

        for file in files:
            file.organization_id = 1  # Assign to default org

        session.commit()
        logger.info(f"✓ Migrated {len(files)} physical files")

        logger.info("=" * 60)
        logger.info("Migration completed successfully!")
        logger.info("=" * 60)
        logger.info("\nNext steps:")
        logger.info("1. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in .env for Google OAuth")
        logger.info("2. Set MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET in .env for Microsoft OAuth")
        logger.info("3. Set ENCRYPTION_KEY in .env for token encryption")
        logger.info("4. Restart the backend server")
        logger.info("\nGenerate encryption key with:")
        logger.info("  from cryptography.fernet import Fernet")
        logger.info("  print(Fernet.generate_key().decode())")

    except Exception as e:
        logger.error(f"Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    run_migration()
