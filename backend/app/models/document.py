from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)

    # Multi-tenancy: Documents belong to organizations
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True, index=True)

    # NEW: Link to PhysicalFile for deduplication
    physical_file_id = Column(Integer, ForeignKey("physical_files.id"), nullable=True, index=True)

    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=True)  # Nullable until template matched
    filename = Column(String, nullable=False)

    # DEPRECATED: file_path now comes from PhysicalFile relationship
    # Kept for backwards compatibility during migration
    file_path = Column(String, nullable=True)

    # Status flow: uploaded → analyzing → template_matched → processing → completed → verified
    # Also: template_needed (no match), error
    status = Column(String, default="uploaded")

    # Template matching
    suggested_template_id = Column(Integer, ForeignKey("schema_templates.id"), nullable=True)
    template_confidence = Column(Float, nullable=True)  # How confident we are in the template match

    # Processing metadata
    # DEPRECATED: Parse cache now on PhysicalFile for sharing across Documents
    # Kept for backwards compatibility during migration
    reducto_job_id = Column(String, nullable=True)  # For pipelining: Parse job ID
    reducto_parse_result = Column(JSON, nullable=True)  # Cache parse results to avoid re-parsing
    elasticsearch_id = Column(String, nullable=True)

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)

    # Error tracking
    error_message = Column(Text, nullable=True)

    # Ownership and sharing (for permissions)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Document owner
    is_public = Column(Boolean, default=False)  # Public documents visible to all users in org

    # Relationships
    physical_file = relationship("PhysicalFile", back_populates="documents")
    schema = relationship("Schema", back_populates="documents")
    suggested_template = relationship("SchemaTemplate", foreign_keys=[suggested_template_id])
    extracted_fields = relationship("ExtractedField", back_populates="document", cascade="all, delete-orphan")
    created_by = relationship("User", foreign_keys=[created_by_user_id])
    permissions = relationship("DocumentPermission", back_populates="document", cascade="all, delete-orphan")
    share_links = relationship("ShareLink", back_populates="document", cascade="all, delete-orphan")

    @property
    def actual_file_path(self) -> str:
        """Get actual file path, preferring PhysicalFile over legacy field."""
        if self.physical_file:
            return self.physical_file.file_path
        return self.file_path

    @property
    def actual_parse_result(self):
        """Get actual parse result, preferring PhysicalFile over legacy field."""
        if self.physical_file and self.physical_file.reducto_parse_result:
            return self.physical_file.reducto_parse_result
        return self.reducto_parse_result

    @property
    def actual_job_id(self) -> str:
        """Get actual job ID, preferring PhysicalFile over legacy field."""
        if self.physical_file and self.physical_file.reducto_job_id:
            return self.physical_file.reducto_job_id
        return self.reducto_job_id


class ExtractedField(Base):
    __tablename__ = "extracted_fields"

    id = Column(Integer, primary_key=True, index=True)
    # Support both old (document_id) and new (extraction_id) for backwards compatibility
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)  # Legacy
    extraction_id = Column(Integer, ForeignKey("extractions.id"), nullable=True)  # New
    field_name = Column(String, nullable=False)

    # Simple types: Use field_value (text, date, number, boolean)
    field_value = Column(Text, nullable=True)

    # Complex types: Use field_value_json (array, table, array_of_objects)
    field_value_json = Column(JSON, nullable=True)

    # Field type: "text", "date", "number", "boolean", "array", "table", "array_of_objects"
    field_type = Column(String, default="text", nullable=False)

    confidence_score = Column(Float, nullable=True)
    needs_verification = Column(Boolean, default=False)
    verified = Column(Boolean, default=False)
    verified_value = Column(Text, nullable=True)
    verified_value_json = Column(JSON, nullable=True)  # For complex types

    # Source information for highlighting in PDF
    source_page = Column(Integer, nullable=True)
    source_bbox = Column(JSON, nullable=True)  # Bounding box coordinates

    # Timestamps
    extracted_at = Column(DateTime, default=datetime.utcnow)
    verified_at = Column(DateTime, nullable=True)

    # NEW: Validation metadata (added 2025-11-05)
    validation_status = Column(String, default="valid", nullable=False)  # "valid", "warning", "error"
    validation_errors = Column(JSON, nullable=True)  # List of error messages
    validation_checked_at = Column(DateTime, nullable=True)

    # Relationships
    document = relationship("Document", back_populates="extracted_fields")  # Legacy
    extraction = relationship("Extraction", back_populates="extracted_fields")  # New
    verifications = relationship("Verification", back_populates="extracted_field", cascade="all, delete-orphan")

    @property
    def audit_priority(self) -> int:
        """
        Calculate audit priority (lower = more urgent)

        Priority levels:
        0 = Critical (low confidence + validation error)
        1 = High (low confidence OR validation error)
        2 = Medium (medium confidence)
        3 = Low (high confidence, valid, optional review)

        Returns:
            int: Priority level (0-3)
        """
        confidence = self.confidence_score or 0.0
        has_low_confidence = confidence < 0.6
        has_validation_error = self.validation_status == "error"
        has_medium_confidence = 0.6 <= confidence < 0.8

        if has_low_confidence and has_validation_error:
            return 0  # CRITICAL - both issues present
        elif has_low_confidence or has_validation_error:
            return 1  # HIGH - one major issue
        elif has_medium_confidence or self.validation_status == "warning":
            return 2  # MEDIUM - borderline confidence or minor validation issue
        else:
            return 3  # LOW - optional quality check

    @property
    def priority_label(self) -> str:
        """Get human-readable priority label"""
        labels = {0: "critical", 1: "high", 2: "medium", 3: "low"}
        return labels.get(self.audit_priority, "unknown")
