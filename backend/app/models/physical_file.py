from sqlalchemy import Column, Integer, String, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class PhysicalFile(Base):
    """
    Represents the actual uploaded file on disk.
    One physical file can have multiple extractions with different templates.
    """
    __tablename__ = "physical_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)  # Original: "contract.pdf"
    file_hash = Column(String, unique=True, index=True)  # SHA256 for deduplication
    file_path = Column(String, unique=True, nullable=False)  # "uploads/abc123_contract.pdf"
    file_size = Column(Integer)
    mime_type = Column(String)

    # Reducto parsing (shared across all extractions of this file)
    reducto_job_id = Column(String, nullable=True)
    reducto_parse_result = Column(JSON, nullable=True)

    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    extractions = relationship("Extraction", back_populates="physical_file", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="physical_file")  # For bulk upload flow

    def __repr__(self):
        return f"<PhysicalFile(id={self.id}, filename='{self.filename}', hash='{self.file_hash[:8]}...')>"
