"""Background job model for tracking long-running tasks"""

from sqlalchemy import JSON, Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class BackgroundJob(Base):
    """
    Model for tracking background jobs (field extraction, re-processing, etc.)

    Used to provide progress updates to users for long-running operations.
    """
    __tablename__ = "background_jobs"

    id = Column(Integer, primary_key=True, index=True)

    # Job type (e.g., "field_extraction", "template_migration")
    type = Column(String, nullable=False, index=True)

    # Status: "running", "completed", "failed", "cancelled"
    status = Column(String, nullable=False, default="running", index=True)

    # Progress tracking
    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)

    # Job data (JSON field for flexible data storage)
    # Example: {"template_id": 123, "field_name": "payment_terms", "started_at": "..."}
    # Note: Can't use 'metadata' as field name (reserved by SQLAlchemy)
    job_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Error message (if failed)
    error_message = Column(String, nullable=True)

    def __repr__(self):
        return f"<BackgroundJob(id={self.id}, type={self.type}, status={self.status}, progress={self.processed_items}/{self.total_items})>"

    @property
    def progress_percentage(self) -> float:
        """Calculate progress as percentage (0.0 - 1.0)"""
        if self.total_items == 0:
            return 0.0
        return self.processed_items / self.total_items

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses"""
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status,
            "total_items": self.total_items,
            "processed_items": self.processed_items,
            "progress": self.progress_percentage,
            "metadata": self.job_data,  # Expose as 'metadata' in API for backwards compat
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message
        }
