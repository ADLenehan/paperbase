from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.template import SchemaTemplate
from app.data.templates import BUILTIN_TEMPLATES
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("/")
async def list_templates(db: Session = Depends(get_db)):
    """
    List all available schema templates

    Returns templates sorted by:
    1. Usage count (most popular first)
    2. Category (invoices, contracts, etc.)
    """
    templates = db.query(SchemaTemplate).order_by(
        SchemaTemplate.usage_count.desc(),
        SchemaTemplate.category
    ).all()

    # If no templates exist, seed the database
    if not templates:
        logger.info("No templates found, seeding built-in templates")
        templates = seed_builtin_templates(db)

    return {
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "category": t.category,
                "description": t.description,
                "icon": t.icon,
                "field_count": len(t.fields),
                "usage_count": t.usage_count,
                "is_builtin": t.is_builtin
            }
            for t in templates
        ]
    }


@router.get("/{template_id}")
async def get_template(template_id: int, db: Session = Depends(get_db)):
    """Get full template details including all fields"""
    template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    return {
        "id": template.id,
        "name": template.name,
        "category": template.category,
        "description": template.description,
        "icon": template.icon,
        "fields": template.fields,
        "is_builtin": template.is_builtin,
        "usage_count": template.usage_count
    }


@router.get("/category/{category}")
async def get_templates_by_category(category: str, db: Session = Depends(get_db)):
    """Get all templates in a specific category"""
    templates = db.query(SchemaTemplate).filter(
        SchemaTemplate.category == category
    ).all()

    return {
        "category": category,
        "templates": [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "icon": t.icon,
                "field_count": len(t.fields)
            }
            for t in templates
        ]
    }


@router.post("/{template_id}/use")
async def track_template_usage(template_id: int, db: Session = Depends(get_db)):
    """Increment usage count when template is selected"""
    template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()

    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    template.usage_count += 1
    db.commit()

    return {"success": True, "usage_count": template.usage_count}


@router.post("/seed")
async def seed_templates(db: Session = Depends(get_db)):
    """
    Seed database with built-in templates (admin only in production)
    This endpoint should be protected in production
    """
    templates = seed_builtin_templates(db)

    return {
        "success": True,
        "message": f"Seeded {len(templates)} templates",
        "templates": [t.name for t in templates]
    }


def seed_builtin_templates(db: Session) -> list[SchemaTemplate]:
    """Helper function to seed built-in templates"""
    seeded_templates = []

    for template_data in BUILTIN_TEMPLATES:
        # Check if template already exists
        existing = db.query(SchemaTemplate).filter(
            SchemaTemplate.name == template_data["name"]
        ).first()

        if existing:
            logger.debug(f"Template '{template_data['name']}' already exists, skipping")
            seeded_templates.append(existing)
            continue

        # Create new template
        template = SchemaTemplate(
            name=template_data["name"],
            category=template_data["category"],
            description=template_data["description"],
            icon=template_data["icon"],
            fields=template_data["fields"],
            is_builtin=True,
            usage_count=0
        )

        db.add(template)
        seeded_templates.append(template)
        logger.info(f"Created template: {template.name}")

    db.commit()

    for template in seeded_templates:
        db.refresh(template)

    return seeded_templates
