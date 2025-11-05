from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Schema(Base):
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    fields = Column(JSON, nullable=False)  # List of field definitions

    # Template-level search guidance (NEW - for semantic field mapping)
    description = Column(String, nullable=True)  # What this template extracts (e.g., "Marketing one-sheets for cloud products")
    search_hints = Column(JSON, nullable=True)  # List of concepts covered by extracted fields (e.g., ["product name", "cloud platform", "pricing"])
    not_extracted = Column(JSON, nullable=True)  # List of concepts NOT in fields, use full_text (e.g., ["benefits", "use cases", "testimonials"])

    # Complexity tracking (NEW)
    complexity_score = Column(Integer, nullable=True)  # 0-100+ scale
    auto_generation_confidence = Column(Float, nullable=True)  # 0.0-1.0 from Claude
    complexity_warnings = Column(JSON, nullable=True)  # List of warning strings
    generation_mode = Column(String, nullable=True)  # "auto", "assisted", "manual"

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="schema")
    complexity_overrides = relationship("ComplexityOverride", back_populates="schema", cascade="all, delete-orphan")


class ComplexityOverride(Base):
    """
    Track when users override complexity recommendations.
    Used for analytics and calibrating complexity scoring.
    """
    __tablename__ = "complexity_overrides"

    id = Column(Integer, primary_key=True, index=True)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=False)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)

    # System recommendation
    complexity_score = Column(Integer, nullable=False)
    recommended_action = Column(String, nullable=False)  # "auto", "assisted", "manual"

    # User action
    user_action = Column(String, nullable=False)  # What user actually chose
    override_reason = Column(String, nullable=True)

    # Outcome metrics (filled in after processing)
    schema_accuracy = Column(Float, nullable=True)  # Measured accuracy 0.0-1.0
    user_corrections_count = Column(Integer, default=0)  # How many fields user edited
    extraction_success = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    schema = relationship("Schema", back_populates="complexity_overrides")


class FieldDefinition:
    """
    Field definition model (stored as JSON in Schema.fields)

    Example for simple field:
    {
        "name": "effective_date",
        "type": "date",
        "required": true,
        "extraction_hints": ["Effective Date:", "Dated:", "As of"],
        "confidence_threshold": 0.75,
        "description": "Contract effective date"
    }

    Example for array field:
    {
        "name": "colors",
        "type": "array",
        "item_type": "text",
        "required": false,
        "extraction_hints": ["Colors:", "Available in:"],
        "confidence_threshold": 0.7,
        "description": "Available color options"
    }

    Example for table field:
    {
        "name": "grading_table",
        "type": "table",
        "required": true,
        "table_schema": {
            "row_identifier": "pom_code",
            "columns": ["size_2", "size_3", "size_4", "size_5"],
            "dynamic_columns": true,
            "column_pattern": "size_.*",
            "value_type": "number"
        },
        "extraction_hints": ["POM Code", "Grading Table", "Measurements"],
        "confidence_threshold": 0.7,
        "description": "Garment size measurements by POM code"
    }

    Example for array_of_objects:
    {
        "name": "line_items",
        "type": "array_of_objects",
        "required": true,
        "object_schema": {
            "description": {"type": "text", "required": true},
            "quantity": {"type": "number", "required": true},
            "unit_price": {"type": "number", "required": true},
            "total": {"type": "number", "required": false}
        },
        "extraction_hints": ["Items:", "Line Items", "Description"],
        "confidence_threshold": 0.75,
        "description": "Invoice line items"
    }
    """
    pass
