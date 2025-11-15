"""
Query History Model

Tracks AI-generated answers and the source documents used to generate them.
Allows users to view which documents contributed to a specific answer.
"""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import JSON, Column, DateTime, String, Text

from app.core.database import Base


class QueryHistory(Base):
    """
    Stores AI query results with links to source documents.

    Enables features like:
    - "Show me all documents used in this answer"
    - Query result caching
    - Answer audit trail
    """
    __tablename__ = "query_history"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Query details
    query_text = Column(Text, nullable=False, index=True)
    query_source = Column(String, nullable=False)  # 'ask_ai' or 'mcp'

    # Source documents (array of document IDs)
    document_ids = Column(JSON, nullable=False)  # List[int]

    # Generated answer
    answer = Column(Text, nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=True)  # Optional TTL for cleanup

    def __repr__(self):
        return f"<QueryHistory(id={self.id}, query='{self.query_text[:50]}...', source={self.query_source})>"

    @property
    def is_expired(self) -> bool:
        """Check if this query has expired"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at

    @classmethod
    def create_from_search(
        cls,
        query: str,
        answer: str,
        document_ids: list,
        source: str = "ask_ai",
        ttl_days: int = 30
    ):
        """
        Create a new query history entry.

        Args:
            query: The natural language query
            answer: The AI-generated answer
            document_ids: List of document IDs used in answer
            source: Source of query ('ask_ai' or 'mcp')
            ttl_days: Days until this entry expires (default: 30)

        Returns:
            QueryHistory instance
        """
        expires_at = datetime.utcnow() + timedelta(days=ttl_days) if ttl_days else None

        return cls(
            query_text=query,
            query_source=source,
            document_ids=document_ids,
            answer=answer,
            expires_at=expires_at
        )
