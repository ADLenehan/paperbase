from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Schema(Base):
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    fields = Column(JSON, nullable=False)  # List of field definitions
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    documents = relationship("Document", back_populates="schema")


class FieldDefinition:
    """
    Field definition model (stored as JSON in Schema.fields)

    Example:
    {
        "name": "effective_date",
        "type": "date",
        "required": true,
        "extraction_hints": ["Effective Date:", "Dated:", "As of"],
        "confidence_threshold": 0.75,
        "description": "Contract effective date"
    }
    """
    pass
