from sqlalchemy import Column, Integer, String, JSON, DateTime, Float, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=True)  # Nullable until template matched
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    # Status flow: uploaded → analyzing → template_matched → processing → completed → verified
    # Also: template_needed (no match), error
    status = Column(String, default="uploaded")

    # Template matching
    suggested_template_id = Column(Integer, ForeignKey("schema_templates.id"), nullable=True)
    template_confidence = Column(Float, nullable=True)  # How confident we are in the template match

    # Processing metadata
    reducto_job_id = Column(String, nullable=True)  # For pipelining: Parse job ID
    reducto_parse_result = Column(JSON, nullable=True)  # Cache parse results to avoid re-parsing
    elasticsearch_id = Column(String, nullable=True)

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Relationships
    schema = relationship("Schema", back_populates="documents")
    suggested_template = relationship("SchemaTemplate", foreign_keys=[suggested_template_id])
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, index=True)
    # Support both old (document_id) and new (extraction_id) for backwards compatibility
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # Legacy
    extraction_id = Column(Integer, ForeignKey("extractions.id"), nullable=True)  # New
    field_name = Column(String, nullable=False)
    field_value = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    needs_verification = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)
    verified_value = Column(Text, nullable=True)

    # Source information for highlighting in PDF
    source_page = Column(Integer, nullable=True)
    source_bbox = Column(JSON, nullable=True)  # Bounding box coordinates

    # Timestamps
    extracted_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="extracted_fields")  # Legacy
    extraction = relationship("Extraction", back_populates="extracted_fields")  # New
    verifications = relationship("Verification", back_populates="extracted_field", cascade="all, delete-orphan")
