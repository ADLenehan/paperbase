from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class Verification(Base):
    __tablename__ = "verifications"

    id = Column(Integer, primary_key=True, index=True)
    extracted_field_id = Column(Integer, ForeignKey("extracted_fields.id"), nullable=False)

    # Original extraction
    original_value = Column(Text, nullable=True)
    original_confidence = Column(Float, nullable=True)

    # User verification
    verified_value = Column(Text, nullable=False)
    verification_type = Column(String, nullable=False)  # correct, incorrect, not_found, custom

    # Session tracking
    session_id = Column(String, nullable=True)
    reviewer_notes = Column(Text, nullable=True)

    # Timestamp
    verified_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    extracted_field = relationship("ExtractedField", back_populates="verifications")


class VerificationSession(Base):
    __tablename__ = "verification_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=False)

    # Statistics
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    correct_count = Column(Integer, default=0)
    incorrect_count = Column(Integer, default=0)

    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
