from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


# Association table for many-to-many relationship between batches and extractions
batch_extractions = Table(
    'batch_extractions',
    Base.metadata,
    Column('batch_id', Integer, ForeignKey('batches.id'), primary_key=True),
    Column('extraction_id', Integer, ForeignKey('extractions.id'), primary_key=True)
)


class Batch(Base):
    """
    Represents a batch processing job for multiple files with one template.
    Used for bulk upload workflows.
    """
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # "Q3 2025 Invoices"
    template_id = Column(Integer, ForeignKey("schema_templates.id"), nullable=True)

    # Status tracking
    status = Column(String, default="pending")  # pending, processing, completed, error
    total_files = Column(Integer, default=0)
    processed_files = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    extractions = relationship("Extraction", secondary=batch_extractions, backref="batches")
    template = relationship("SchemaTemplate")

    def __repr__(self):
        return f"<Batch(id={self.id}, name='{self.name}', status='{self.status}', {self.processed_files}/{self.total_files})>"
