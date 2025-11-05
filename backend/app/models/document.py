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

    # NEW: Citation and provenance tracking for MCP
    source_text = Column(Text, nullable=True)  # Actual text extracted from PDF
    source_block_ids = Column(JSON, nullable=True)  # Array of block IDs from parse result
    context_before = Column(Text, nullable=True)  # Text appearing before extraction (200 chars)
    context_after = Column(Text, nullable=True)  # Text appearing after extraction (200 chars)
    extraction_method = Column(String, nullable=True)  # 'reducto_structured', 'reducto_parse', 'claude', 'manual'

    # Timestamps
    extracted_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="extracted_fields")  # Legacy
    extraction = relationship("Extraction", back_populates="extracted_fields")  # New
    verifications = relationship("Verification", back_populates="extracted_field", cascade="all, delete-orphan")


class DocumentBlock(Base):
    """
    Structured storage of Reducto parse result blocks for citation and retrieval.

    Each block represents a chunk from the Reducto parse API with full context.
    Used for:
    - Linking extractions to source text
    - Vector search (future)
    - Citation generation for MCP
    - RAG retrieval (future)
    """
    __tablename__ = "document_blocks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)

    # Block identification
    block_id = Column(String, nullable=True)  # ID from Reducto parse result
    block_type = Column(String, nullable=True)  # 'text', 'table', 'image', 'title', 'list'
    block_index = Column(Integer, nullable=False)  # Order in document (0-indexed)

    # Content
    text_content = Column(Text, nullable=True)  # Main text content
    confidence = Column(Float, nullable=True)  # Reducto's logprobs_confidence

    # Location
    page = Column(Integer, nullable=False)
    bbox = Column(JSON, nullable=True)  # {x, y, width, height}

    # Context for citation (helps LLMs understand surrounding text)
    context_before = Column(Text, nullable=True)  # Previous 200 chars
    context_after = Column(Text, nullable=True)  # Next 200 chars

    # Metadata
    parse_metadata = Column(JSON, nullable=True)  # Full block metadata from Reducto

    # Future: Vector embedding for semantic search
    # embedding = Column(Vector(1536), nullable=True)  # Requires pgvector extension

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    document = relationship("Document", backref="blocks")
