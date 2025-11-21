"""
Canonical field mapping models for cross-template aggregations.

Allows users to define semantic mappings between fields across different templates.
Example: "revenue" → {Invoice: invoice_total, Receipt: payment_amount, Contract: contract_value}
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, JSON, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from app.core.database import Base


class CanonicalFieldMapping(Base):
    """
    User-defined canonical field mappings for cross-template aggregations.

    A canonical mapping groups semantically equivalent fields across templates under a single name.

    Example:
        canonical_name = "revenue"
        field_mappings = {
            "Invoice": "invoice_total",
            "Receipt": "payment_amount",
            "Contract": "contract_value"
        }
        aggregation_type = "sum"

    When a user queries "total revenue", the system will:
    1. Detect "revenue" is a canonical field
    2. Expand to SUM(invoice_total + payment_amount + contract_value)
    3. Return aggregated result across all templates
    """
    __tablename__ = "canonical_field_mappings"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String, unique=True, nullable=False, index=True)  # "revenue", "vendor", "date"
    description = Column(String, nullable=True)  # Human-readable description
    field_mappings = Column(JSON, nullable=False)  # {template_name: field_name}
    aggregation_type = Column(String, nullable=False)  # "sum", "avg", "count", "terms", etc.
    is_system = Column(Boolean, default=False)  # System-defined vs user-defined
    is_active = Column(Boolean, default=True)  # Soft delete

    # Metadata
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by])

    def __repr__(self):
        return f"<CanonicalFieldMapping(name='{self.canonical_name}', type='{self.aggregation_type}')>"

    def get_field_for_template(self, template_name: str) -> str | None:
        """Get the mapped field name for a specific template."""
        return self.field_mappings.get(template_name)

    def get_all_fields(self) -> list[str]:
        """Get all field names across all templates."""
        return list(self.field_mappings.values())

    def get_templates(self) -> list[str]:
        """Get all template names in this mapping."""
        return list(self.field_mappings.keys())


class CanonicalAlias(Base):
    """
    Aliases for canonical field names to improve natural language understanding.

    Example:
        canonical_field_id = 1  # Points to "revenue" mapping
        alias = "sales"

    When user asks "total sales", system maps "sales" → "revenue" → field_mappings
    """
    __tablename__ = "canonical_aliases"

    id = Column(Integer, primary_key=True, index=True)
    canonical_field_id = Column(Integer, ForeignKey("canonical_field_mappings.id", ondelete="CASCADE"), nullable=False)
    alias = Column(String, nullable=False, index=True)  # "sales", "income", "spend", etc.
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    canonical_field = relationship("CanonicalFieldMapping", backref="aliases")

    def __repr__(self):
        return f"<CanonicalAlias(alias='{self.alias}', canonical_id={self.canonical_field_id})>"
