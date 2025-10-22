from sqlalchemy import Column, Integer, String, JSON, DateTime, Boolean
from sqlalchemy.sql import func
from app.core.database import Base


class SchemaTemplate(Base):
    """
    Pre-built schema templates for common document types.

    Templates provide a starting point for users, reducing time-to-value
    and encoding best practices for extraction.
    """
    __tablename__ = "schema_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    category = Column(String, nullable=False, index=True)  # invoice, contract, receipt, etc.
    description = Column(String, nullable=False)
    icon = Column(String, default="📄")

    # Template schema structure
    fields = Column(JSON, nullable=False)  # Array of field configs

    # Metadata
    is_builtin = Column(Boolean, default=True)  # Built-in vs user-created
    usage_count = Column(Integer, default=0)  # Track popularity

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<SchemaTemplate(name='{self.name}', category='{self.category}')>"
