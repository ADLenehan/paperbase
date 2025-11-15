"""
Settings API endpoints.

For MVP:
- All requests use default org/user (id=1)
- Future: Extract org_id/user_id from JWT token
"""

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.settings import DEFAULT_SETTINGS
from app.services.settings_service import SettingsService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingUpdateRequest(BaseModel):
    """Request to update a setting."""
    key: str
    value: Any
    value_type: str = Field(..., pattern="^(float|int|bool|string|json)$")
    description: Optional[str] = None


class SettingResponse(BaseModel):
    """Response for a single setting."""
    key: str
    value: Any
    value_type: str
    source: str  # "user", "organization", "system", "default"
    description: Optional[str] = None
    category: Optional[str] = None
    min: Optional[float] = None
    max: Optional[float] = None


class SettingsListResponse(BaseModel):
    """Response for list of all settings."""
    settings: List[SettingResponse]
    org_id: int
    user_id: int
    org_name: str
    user_email: str


def get_default_context(db: Session):
    """
    Get default org and user for MVP.

    Future: Replace with JWT token extraction.
    """
    settings_service = SettingsService(db)
    org = settings_service.get_or_create_default_org()
    user = settings_service.get_or_create_default_user(org.id)
    return org, user


@router.get("/")
async def get_all_settings(
    include_metadata: bool = Query(True, description="Include metadata like source, description, etc."),
    db: Session = Depends(get_db)
) -> SettingsListResponse:
    """
    Get all settings with hierarchical resolution.

    Returns settings resolved for the current user/org context.
    """
    org, user = get_default_context(db)
    settings_service = SettingsService(db)

    # Get all settings with metadata
    settings_dict = settings_service.get_all_settings(
        user_id=user.id,
        org_id=org.id,
        include_metadata=True
    )

    # Format response
    settings_list = []
    for key, data in settings_dict.items():
        settings_list.append(SettingResponse(
            key=key,
            value=data["value"],
            value_type=data["type"],
            source=data.get("source", "default"),
            description=data.get("description"),
            category=data.get("category"),
            min=data.get("min"),
            max=data.get("max")
        ))

    return SettingsListResponse(
        settings=settings_list,
        org_id=org.id,
        user_id=user.id,
        org_name=org.name,
        user_email=user.email
    )


@router.get("/{key}")
async def get_setting(
    key: str,
    db: Session = Depends(get_db)
) -> SettingResponse:
    """
    Get a specific setting value.

    Returns the resolved value for the current user/org context.
    """
    org, user = get_default_context(db)
    settings_service = SettingsService(db)

    # Get resolved value
    value = settings_service.get_setting(
        key=key,
        user_id=user.id,
        org_id=org.id
    )

    if value is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")

    # Get metadata from DEFAULT_SETTINGS if available
    metadata = DEFAULT_SETTINGS.get(key, {})

    # Determine source
    source = "default"
    if settings_service.db.query(settings_service.db.query(Settings).filter(
        Settings.key == key,
        Settings.user_id == user.id,
        Settings.org_id == org.id
    ).exists()).scalar():
        source = "user"
    elif settings_service.db.query(settings_service.db.query(Settings).filter(
        Settings.key == key,
        Settings.org_id == org.id,
        Settings.user_id.is_(None)
    ).exists()).scalar():
        source = "organization"
    elif settings_service.db.query(settings_service.db.query(Settings).filter(
        Settings.key == key,
        Settings.org_id.is_(None),
        Settings.user_id.is_(None)
    ).exists()).scalar():
        source = "system"

    return SettingResponse(
        key=key,
        value=value,
        value_type=metadata.get("type", "string"),
        source=source,
        description=metadata.get("description"),
        category=metadata.get("category"),
        min=metadata.get("min"),
        max=metadata.get("max")
    )


@router.put("/{key}")
async def update_setting(
    key: str,
    request: SettingUpdateRequest,
    level: str = Query("organization", pattern="^(system|organization|user)$", description="Setting level"),
    db: Session = Depends(get_db)
):
    """
    Update a setting at the specified level.

    Levels:
    - "system": System-wide default (requires admin)
    - "organization": Organization-level (default for MVP)
    - "user": User-level override
    """
    org, user = get_default_context(db)
    settings_service = SettingsService(db)

    # Validate key exists in defaults
    if key not in DEFAULT_SETTINGS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown setting key '{key}'. Valid keys: {list(DEFAULT_SETTINGS.keys())}"
        )

    # Validate value type matches expected type
    expected_type = DEFAULT_SETTINGS[key]["type"]
    if request.value_type != expected_type:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid value_type for '{key}'. Expected '{expected_type}', got '{request.value_type}'"
        )

    # Validate value range if applicable
    if "min" in DEFAULT_SETTINGS[key] and "max" in DEFAULT_SETTINGS[key]:
        min_val = DEFAULT_SETTINGS[key]["min"]
        max_val = DEFAULT_SETTINGS[key]["max"]
        if not (min_val <= request.value <= max_val):
            raise HTTPException(
                status_code=400,
                detail=f"Value for '{key}' must be between {min_val} and {max_val}"
            )

    # Determine scope
    org_id = None
    user_id = None

    if level == "organization":
        org_id = org.id
    elif level == "user":
        org_id = org.id
        user_id = user.id
    # system level: both None

    # Update setting
    try:
        setting = settings_service.set_setting(
            key=key,
            value=request.value,
            value_type=request.value_type,
            org_id=org_id,
            user_id=user_id,
            description=request.description or DEFAULT_SETTINGS[key].get("description")
        )

        return {
            "success": True,
            "message": f"Setting '{key}' updated at {level} level",
            "setting": {
                "key": setting.key,
                "value": settings_service._deserialize_value(setting.value, setting.value_type),
                "level": level
            }
        }
    except Exception as e:
        logger.error(f"Failed to update setting: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{key}")
async def delete_setting(
    key: str,
    level: str = Query("organization", pattern="^(system|organization|user)$", description="Setting level"),
    db: Session = Depends(get_db)
):
    """
    Delete a setting at the specified level.

    This will cause the setting to fall back to the next level in the hierarchy.
    """
    org, user = get_default_context(db)
    settings_service = SettingsService(db)

    # Determine scope
    org_id = None
    user_id = None

    if level == "organization":
        org_id = org.id
    elif level == "user":
        org_id = org.id
        user_id = user.id

    # Delete setting
    deleted = settings_service.delete_setting(
        key=key,
        org_id=org_id,
        user_id=user_id
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Setting '{key}' not found at {level} level"
        )

    return {
        "success": True,
        "message": f"Setting '{key}' deleted at {level} level. Will now use fallback value."
    }


@router.post("/initialize")
async def initialize_defaults(
    db: Session = Depends(get_db)
):
    """
    Initialize system default settings.

    Creates system-level defaults from DEFAULT_SETTINGS if they don't exist.
    Safe to call multiple times (idempotent).
    """
    settings_service = SettingsService(db)

    try:
        settings_service.initialize_defaults()
        return {
            "success": True,
            "message": "System defaults initialized",
            "count": len(DEFAULT_SETTINGS)
        }
    except Exception as e:
        logger.error(f"Failed to initialize defaults: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories/list")
async def get_categories():
    """
    Get list of all setting categories.

    Useful for organizing settings UI into tabs/sections.
    """
    categories = set()
    for config in DEFAULT_SETTINGS.values():
        if "category" in config:
            categories.add(config["category"])

    return {
        "categories": sorted(list(categories))
    }


@router.get("/category/{category}")
async def get_settings_by_category(
    category: str,
    db: Session = Depends(get_db)
):
    """
    Get all settings in a specific category.
    """
    org, user = get_default_context(db)
    settings_service = SettingsService(db)

    # Get all settings
    all_settings = settings_service.get_all_settings(
        user_id=user.id,
        org_id=org.id,
        include_metadata=True
    )

    # Filter by category
    filtered = []
    for key, data in all_settings.items():
        if data.get("category") == category:
            filtered.append(SettingResponse(
                key=key,
                value=data["value"],
                value_type=data["type"],
                source=data.get("source", "default"),
                description=data.get("description"),
                category=data.get("category"),
                min=data.get("min"),
                max=data.get("max")
            ))

    return {
        "category": category,
        "settings": filtered
    }
