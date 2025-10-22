"""
Settings service for hierarchical settings resolution.

Resolution order:
1. User-level settings (highest priority)
2. Organization-level settings
3. System defaults
4. Hardcoded defaults (from models.settings.DEFAULT_SETTINGS)
"""

from sqlalchemy.orm import Session
from app.models.settings import Settings, Organization, User, DEFAULT_SETTINGS
from typing import Optional, Any, Dict
import json
import logging

logger = logging.getLogger(__name__)


class SettingsService:
    """Service for managing and resolving hierarchical settings."""

    def __init__(self, db: Session):
        self.db = db

    def get_setting(
        self,
        key: str,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        default: Any = None
    ) -> Any:
        """
        Get setting value with hierarchical resolution.

        Args:
            key: Setting key (e.g., "audit_confidence_threshold")
            user_id: User ID for user-level settings
            org_id: Organization ID for org-level settings
            default: Default value if not found anywhere

        Returns:
            Setting value (typed according to value_type)
        """

        # 1. Try user-level setting
        if user_id and org_id:
            setting = self.db.query(Settings).filter(
                Settings.key == key,
                Settings.user_id == user_id,
                Settings.org_id == org_id
            ).first()

            if setting:
                return self._deserialize_value(setting.value, setting.value_type)

        # 2. Try org-level setting
        if org_id:
            setting = self.db.query(Settings).filter(
                Settings.key == key,
                Settings.org_id == org_id,
                Settings.user_id.is_(None)
            ).first()

            if setting:
                return self._deserialize_value(setting.value, setting.value_type)

        # 3. Try system default
        setting = self.db.query(Settings).filter(
            Settings.key == key,
            Settings.org_id.is_(None),
            Settings.user_id.is_(None)
        ).first()

        if setting:
            return self._deserialize_value(setting.value, setting.value_type)

        # 4. Try hardcoded default
        if key in DEFAULT_SETTINGS:
            return DEFAULT_SETTINGS[key]["value"]

        # 5. Return provided default
        return default

    def get_all_settings(
        self,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        include_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        Get all settings with hierarchical resolution.

        Returns a flat dictionary of key-value pairs with resolved values.
        """
        result = {}

        # Start with hardcoded defaults
        for key, config in DEFAULT_SETTINGS.items():
            result[key] = {
                "value": config["value"],
                "source": "default",
                "type": config["type"],
                "description": config.get("description"),
                "category": config.get("category"),
                "min": config.get("min"),
                "max": config.get("max"),
            } if include_metadata else config["value"]

        # Override with system settings
        system_settings = self.db.query(Settings).filter(
            Settings.org_id.is_(None),
            Settings.user_id.is_(None)
        ).all()

        for setting in system_settings:
            value = self._deserialize_value(setting.value, setting.value_type)
            if include_metadata:
                result[setting.key] = {
                    "value": value,
                    "source": "system",
                    "type": setting.value_type,
                    "description": setting.description,
                }
            else:
                result[setting.key] = value

        # Override with org settings
        if org_id:
            org_settings = self.db.query(Settings).filter(
                Settings.org_id == org_id,
                Settings.user_id.is_(None)
            ).all()

            for setting in org_settings:
                value = self._deserialize_value(setting.value, setting.value_type)
                if include_metadata:
                    result[setting.key] = {
                        "value": value,
                        "source": "organization",
                        "type": setting.value_type,
                        "description": setting.description,
                    }
                else:
                    result[setting.key] = value

        # Override with user settings
        if user_id and org_id:
            user_settings = self.db.query(Settings).filter(
                Settings.user_id == user_id,
                Settings.org_id == org_id
            ).all()

            for setting in user_settings:
                value = self._deserialize_value(setting.value, setting.value_type)
                if include_metadata:
                    result[setting.key] = {
                        "value": value,
                        "source": "user",
                        "type": setting.value_type,
                        "description": setting.description,
                    }
                else:
                    result[setting.key] = value

        return result

    def set_setting(
        self,
        key: str,
        value: Any,
        value_type: str,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None,
        description: Optional[str] = None
    ) -> Settings:
        """
        Set a setting at the specified level.

        Args:
            key: Setting key
            value: Setting value
            value_type: Value type ("float", "int", "bool", "string", "json")
            user_id: User ID (None for org or system level)
            org_id: Organization ID (None for system level)
            description: Human-readable description
        """

        # Validate value type
        if value_type not in ["float", "int", "bool", "string", "json"]:
            raise ValueError(f"Invalid value_type: {value_type}")

        # Check if setting exists
        query = self.db.query(Settings).filter(Settings.key == key)

        if user_id:
            query = query.filter(Settings.user_id == user_id)
        else:
            query = query.filter(Settings.user_id.is_(None))

        if org_id:
            query = query.filter(Settings.org_id == org_id)
        else:
            query = query.filter(Settings.org_id.is_(None))

        setting = query.first()

        # Serialize value
        serialized_value = self._serialize_value(value, value_type)

        if setting:
            # Update existing
            setting.value = serialized_value
            setting.value_type = value_type
            if description:
                setting.description = description
        else:
            # Create new
            setting = Settings(
                key=key,
                value=serialized_value,
                value_type=value_type,
                org_id=org_id,
                user_id=user_id,
                description=description
            )
            self.db.add(setting)

        self.db.commit()
        self.db.refresh(setting)
        return setting

    def delete_setting(
        self,
        key: str,
        user_id: Optional[int] = None,
        org_id: Optional[int] = None
    ) -> bool:
        """
        Delete a setting at the specified level.

        Returns True if deleted, False if not found.
        """
        query = self.db.query(Settings).filter(Settings.key == key)

        if user_id:
            query = query.filter(Settings.user_id == user_id)
        else:
            query = query.filter(Settings.user_id.is_(None))

        if org_id:
            query = query.filter(Settings.org_id == org_id)
        else:
            query = query.filter(Settings.org_id.is_(None))

        setting = query.first()

        if setting:
            self.db.delete(setting)
            self.db.commit()
            return True

        return False

    def initialize_defaults(self) -> None:
        """
        Initialize system default settings from DEFAULT_SETTINGS.

        Only creates settings that don't already exist.
        """
        for key, config in DEFAULT_SETTINGS.items():
            # Check if system default exists
            existing = self.db.query(Settings).filter(
                Settings.key == key,
                Settings.org_id.is_(None),
                Settings.user_id.is_(None)
            ).first()

            if not existing:
                self.set_setting(
                    key=key,
                    value=config["value"],
                    value_type=config["type"],
                    description=config.get("description")
                )
                logger.info(f"Initialized system default: {key} = {config['value']}")

    def get_or_create_default_org(self) -> Organization:
        """Get or create the default organization for MVP."""
        org = self.db.query(Organization).filter(Organization.slug == "default").first()

        if not org:
            org = Organization(
                name="Default Organization",
                slug="default",
                is_active=True
            )
            self.db.add(org)
            self.db.commit()
            self.db.refresh(org)
            logger.info("Created default organization")

        return org

    def get_or_create_default_user(self, org_id: int) -> User:
        """Get or create the default user for MVP."""
        user = self.db.query(User).filter(User.email == "default@paperbase.local").first()

        if not user:
            user = User(
                org_id=org_id,
                email="default@paperbase.local",
                name="Default User",
                is_active=True,
                is_admin=True
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
            logger.info("Created default user")

        return user

    def _serialize_value(self, value: Any, value_type: str) -> str:
        """Serialize value to string for storage."""
        if value_type == "json":
            return json.dumps(value)
        elif value_type == "bool":
            return "true" if value else "false"
        else:
            return str(value)

    def _deserialize_value(self, value: str, value_type: str) -> Any:
        """Deserialize value from string."""
        if value_type == "float":
            return float(value)
        elif value_type == "int":
            return int(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            return json.loads(value)
        else:  # string
            return value
