"""
API endpoints for canonical field mapping management.

Allows users to create, update, and manage cross-template field mappings.
"""
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.canonical_mapping import CanonicalFieldMapping
from app.models.settings import User
from app.services.canonical_field_service import CanonicalFieldService

router = APIRouter(prefix="/api/canonical-fields", tags=["canonical-fields"])


# Request/Response Models

class CanonicalFieldCreate(BaseModel):
    """Request model for creating a canonical field mapping."""
    canonical_name: str = Field(..., description="Canonical name (e.g., 'revenue')")
    description: Optional[str] = Field(None, description="Human-readable description")
    field_mappings: Dict[str, str] = Field(..., description="Template to field name mappings")
    aggregation_type: str = Field(..., description="Default aggregation type (sum, avg, count, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "canonical_name": "revenue",
                "description": "Total revenue across all document types",
                "field_mappings": {
                    "Invoice": "invoice_total",
                    "Receipt": "payment_amount",
                    "Contract": "contract_value"
                },
                "aggregation_type": "sum"
            }
        }


class CanonicalFieldUpdate(BaseModel):
    """Request model for updating a canonical field mapping."""
    description: Optional[str] = None
    field_mappings: Optional[Dict[str, str]] = None
    aggregation_type: Optional[str] = None


class AliasCreate(BaseModel):
    """Request model for adding an alias."""
    alias: str = Field(..., description="Alias to add (e.g., 'sales' for 'revenue')")


class CanonicalFieldResponse(BaseModel):
    """Response model for canonical field mapping."""
    id: int
    canonical_name: str
    description: Optional[str]
    field_mappings: Dict[str, str]
    aggregation_type: str
    is_system: bool
    aliases: List[str]
    templates: List[str]

    class Config:
        from_attributes = True


# Endpoints

@router.get("/", response_model=List[CanonicalFieldResponse])
async def list_canonical_fields(
    include_system: bool = True,
    include_user: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all canonical field mappings.

    Args:
        include_system: Include system-defined mappings
        include_user: Include user-defined mappings

    Returns:
        List of canonical field mappings with aliases
    """
    service = CanonicalFieldService(db)
    mappings = service.list_mappings(
        include_system=include_system,
        include_user=include_user
    )

    results = []
    for mapping in mappings:
        results.append(CanonicalFieldResponse(
            id=mapping.id,
            canonical_name=mapping.canonical_name,
            description=mapping.description,
            field_mappings=mapping.field_mappings,
            aggregation_type=mapping.aggregation_type,
            is_system=mapping.is_system,
            aliases=service.get_aliases_for_canonical(mapping.canonical_name),
            templates=mapping.get_templates()
        ))

    return results


@router.get("/{canonical_name}", response_model=CanonicalFieldResponse)
async def get_canonical_field(
    canonical_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific canonical field mapping by name.

    Args:
        canonical_name: Canonical field name

    Returns:
        Canonical field mapping with aliases
    """
    service = CanonicalFieldService(db)
    mapping = service.get_mapping(canonical_name)

    if not mapping:
        raise HTTPException(status_code=404, detail=f"Canonical field '{canonical_name}' not found")

    return CanonicalFieldResponse(
        id=mapping.id,
        canonical_name=mapping.canonical_name,
        description=mapping.description,
        field_mappings=mapping.field_mappings,
        aggregation_type=mapping.aggregation_type,
        is_system=mapping.is_system,
        aliases=service.get_aliases_for_canonical(canonical_name),
        templates=mapping.get_templates()
    )


@router.post("/", response_model=CanonicalFieldResponse, status_code=201)
async def create_canonical_field(
    data: CanonicalFieldCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new canonical field mapping.

    Args:
        data: Canonical field creation data

    Returns:
        Created canonical field mapping

    Raises:
        HTTPException: If canonical name already exists
    """
    service = CanonicalFieldService(db)

    try:
        mapping = service.create_mapping(
            canonical_name=data.canonical_name,
            field_mappings=data.field_mappings,
            aggregation_type=data.aggregation_type,
            description=data.description,
            created_by=current_user.id
        )

        return CanonicalFieldResponse(
            id=mapping.id,
            canonical_name=mapping.canonical_name,
            description=mapping.description,
            field_mappings=mapping.field_mappings,
            aggregation_type=mapping.aggregation_type,
            is_system=mapping.is_system,
            aliases=[],
            templates=mapping.get_templates()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{canonical_name}", response_model=CanonicalFieldResponse)
async def update_canonical_field(
    canonical_name: str,
    data: CanonicalFieldUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a canonical field mapping.

    Args:
        canonical_name: Canonical field name
        data: Update data

    Returns:
        Updated canonical field mapping

    Raises:
        HTTPException: If mapping not found or is system-defined
    """
    service = CanonicalFieldService(db)

    try:
        mapping = service.update_mapping(
            canonical_name=canonical_name,
            field_mappings=data.field_mappings,
            description=data.description,
            aggregation_type=data.aggregation_type
        )

        return CanonicalFieldResponse(
            id=mapping.id,
            canonical_name=mapping.canonical_name,
            description=mapping.description,
            field_mappings=mapping.field_mappings,
            aggregation_type=mapping.aggregation_type,
            is_system=mapping.is_system,
            aliases=service.get_aliases_for_canonical(canonical_name),
            templates=mapping.get_templates()
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{canonical_name}", status_code=204)
async def delete_canonical_field(
    canonical_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a canonical field mapping (soft delete).

    Args:
        canonical_name: Canonical field name

    Raises:
        HTTPException: If mapping not found or is system-defined
    """
    service = CanonicalFieldService(db)

    try:
        service.delete_mapping(canonical_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{canonical_name}/aliases", status_code=201)
async def add_alias(
    canonical_name: str,
    data: AliasCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Add an alias for a canonical field.

    Args:
        canonical_name: Canonical field name
        data: Alias data

    Returns:
        Success message

    Raises:
        HTTPException: If canonical field not found or alias already exists
    """
    service = CanonicalFieldService(db)

    try:
        service.add_alias(canonical_name, data.alias)
        return {"message": f"Alias '{data.alias}' added to '{canonical_name}'"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{canonical_name}/aliases/{alias}", status_code=204)
async def remove_alias(
    canonical_name: str,
    alias: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Remove an alias from a canonical field.

    Args:
        canonical_name: Canonical field name (not used, but kept for REST consistency)
        alias: Alias to remove

    Raises:
        HTTPException: If alias not found
    """
    service = CanonicalFieldService(db)

    try:
        service.remove_alias(alias)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh-cache", status_code=200)
async def refresh_cache(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Refresh the canonical field cache from database.

    Useful after direct database modifications.

    Returns:
        Success message
    """
    service = CanonicalFieldService(db)
    service.refresh_cache()

    return {"message": "Canonical field cache refreshed"}


@router.get("/{canonical_name}/resolve", response_model=Dict[str, str])
async def resolve_canonical_field(
    canonical_name: str,
    template_name: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Resolve a canonical field to actual field names.

    Args:
        canonical_name: Canonical field name or alias
        template_name: Optional template name to get specific field

    Returns:
        Field mappings or single field name
    """
    service = CanonicalFieldService(db)

    # Resolve alias if needed
    resolved_name = service.resolve_canonical_name(canonical_name)
    if not resolved_name:
        raise HTTPException(status_code=404, detail=f"Canonical field or alias '{canonical_name}' not found")

    if template_name:
        # Get specific template field
        field = service.expand_field_for_template(resolved_name, template_name)
        if not field:
            raise HTTPException(
                status_code=404,
                detail=f"No mapping for template '{template_name}' in canonical field '{resolved_name}'"
            )
        return {"template": template_name, "field": field}
    else:
        # Get all template mappings
        mappings = service.expand_field_all_templates(resolved_name)
        return {"canonical_name": resolved_name, "mappings": mappings}
