"""
Migration script to consolidate settings thresholds.

This script:
1. Renames audit_confidence_threshold -> review_threshold
2. Renames template_matching_threshold -> auto_match_threshold
3. Removes confidence_threshold_high and confidence_threshold_medium
4. Preserves any user/org customizations

Run with: python -m app.migrations.migrate_settings
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy.orm import Session
from app.core.database import engine, SessionLocal
from app.models.settings import Settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_settings(db: Session, dry_run: bool = False):
    """
    Migrate settings to new naming scheme.

    Args:
        db: Database session
        dry_run: If True, only show what would be changed
    """

    # Mapping of old key -> new key
    renames = {
        "audit_confidence_threshold": "review_threshold",
        "template_matching_threshold": "auto_match_threshold",
    }

    # Keys to remove (will be hardcoded in display logic)
    to_remove = [
        "confidence_threshold_high",
        "confidence_threshold_medium",
    ]

    logger.info("=" * 60)
    logger.info(f"Settings Migration {'(DRY RUN)' if dry_run else ''}")
    logger.info("=" * 60)

    # Step 1: Rename settings
    for old_key, new_key in renames.items():
        settings_to_rename = db.query(Settings).filter(Settings.key == old_key).all()

        if settings_to_rename:
            logger.info(f"\n📝 Renaming '{old_key}' -> '{new_key}':")
            for setting in settings_to_rename:
                scope = "system" if not setting.org_id else (
                    "organization" if not setting.user_id else "user"
                )
                logger.info(
                    f"  - {scope} level: value={setting.value} "
                    f"(org_id={setting.org_id}, user_id={setting.user_id})"
                )

                if not dry_run:
                    setting.key = new_key
                    setting.description = setting.description.replace(old_key, new_key) if setting.description else None
        else:
            logger.info(f"\n⏭️  No '{old_key}' settings found to rename")

    # Step 2: Remove obsolete settings
    logger.info(f"\n🗑️  Removing obsolete settings:")
    for key in to_remove:
        settings_to_remove = db.query(Settings).filter(Settings.key == key).all()

        if settings_to_remove:
            logger.info(f"  - Removing {len(settings_to_remove)} '{key}' setting(s)")
            for setting in settings_to_remove:
                scope = "system" if not setting.org_id else (
                    "organization" if not setting.user_id else "user"
                )
                logger.info(f"    • {scope} level: value={setting.value}")

                if not dry_run:
                    db.delete(setting)
        else:
            logger.info(f"  - No '{key}' settings found")

    # Commit changes
    if not dry_run:
        db.commit()
        logger.info("\n✅ Migration completed successfully!")
    else:
        logger.info("\n🔍 Dry run complete. No changes made.")
        logger.info("   Run without --dry-run to apply changes.")

    logger.info("=" * 60)


def rollback_settings(db: Session):
    """
    Rollback migration (reverse the changes).
    """
    logger.info("=" * 60)
    logger.info("Settings Migration Rollback")
    logger.info("=" * 60)

    # Reverse renames
    reverse_renames = {
        "review_threshold": "audit_confidence_threshold",
        "auto_match_threshold": "template_matching_threshold",
    }

    for current_key, old_key in reverse_renames.items():
        settings_to_rename = db.query(Settings).filter(Settings.key == current_key).all()

        if settings_to_rename:
            logger.info(f"\n📝 Reverting '{current_key}' -> '{old_key}':")
            for setting in settings_to_rename:
                logger.info(f"  - Renaming back: value={setting.value}")
                setting.key = old_key
        else:
            logger.info(f"\n⏭️  No '{current_key}' settings found to revert")

    # Note: We don't restore removed settings as they're not critical
    logger.info("\n⚠️  Note: Removed settings (confidence_threshold_high/medium) are NOT restored")
    logger.info("   These are now hardcoded in the display logic")

    db.commit()
    logger.info("\n✅ Rollback completed!")
    logger.info("=" * 60)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Migrate settings to new naming scheme")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without making changes"
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Rollback the migration (reverse changes)"
    )

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.rollback:
            rollback_settings(db)
        else:
            migrate_settings(db, dry_run=args.dry_run)
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()
