from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Extraction(Base):
    """
    Represents a single extraction job: one physical file processed with one template.
    A physical file can have multiple extractions (different templates).
    """
    __tablename__ = "extractions"

    id = Column(Integer, primary_key=True, index=True)
    physical_file_id = Column(Integer, ForeignKey("physical_files.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("schema_templates.id"), nullable=False)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=True)  # Assigned schema instance

    # Processing status
    # Flow: pending → processing → completed → verified
    # Also: error, template_needed
    status = Column(String, default="pending", index=True)
    template_confidence = Column(Float, nullable=True)

    # Virtual folder organization (metadata only - no file duplication!)
    # Example: "Invoice/2025-10-11/contract.pdf"
    organized_path = Column(String, index=True)

    # Elasticsearch
    elasticsearch_id = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Relationships
    physical_file = relationship("PhysicalFile", back_populates="extractions")
    template = relationship("SchemaTemplate")
    schema = relationship("Schema")
    extracted_fields = relationship("ExtractedField", back_populates="extraction", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Extraction(id={self.id}, file='{self.physical_file.filename if self.physical_file else 'N/A'}', template='{self.template.name if self.template else 'N/A'}')>"
