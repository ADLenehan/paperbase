from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Float, Integer, String

from app.core.database import Base


class QueryPattern(Base):
    """
    Stores cached query patterns to reduce LLM API calls.

    When a user asks "show me invoices over $1000", we cache the pattern
    "show me {template} over ${amount}" so future similar queries can
    reuse the Elasticsearch query structure without calling Claude.
    """
    __tablename__ = "query_patterns"

    id = Column(Integer, primary_key=True, index=True)

    # Pattern matching
    pattern = Column(String, index=True, nullable=False)  # e.g., "invoices over $X"
    template_name = Column(String, index=True)  # Template this pattern applies to
    query_type = Column(String, index=True)  # search, aggregation, anomaly, comparison

    # Query structure
    es_query_template = Column(JSON, nullable=False)  # Reusable ES query with placeholders
    explanation_template = Column(String)  # e.g., "Searching for {template} with amount > {X}"

    # Parameters
    parameter_names = Column(JSON)  # ["amount", "date_from", "date_to"]
    parameter_types = Column(JSON)  # {"amount": "float", "date_from": "date"}

    # Usage tracking
    usage_count = Column(Integer, default=0)
    success_rate = Column(Float, default=1.0)  # Track if queries work well
    last_used = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Confidence
    confidence_score = Column(Float, default=0.8)  # How confident we are in this pattern

    def __repr__(self):
        return f"<QueryPattern(pattern='{self.pattern}', template='{self.template_name}', uses={self.usage_count})>"


class QueryCache(Base):
    """
    Stores exact query results for even faster lookups.

    This is for exact query matches with specific parameter values,
    while QueryPattern is for pattern-based matching.
    """
    __tablename__ = "query_cache"

    id = Column(Integer, primary_key=True, index=True)

    # Query identification
    query_hash = Column(String, index=True, unique=True, nullable=False)  # Hash of query + params
    original_query = Column(String, nullable=False)
    template_name = Column(String, index=True)

    # Cached data
    es_query = Column(JSON, nullable=False)
    explanation = Column(String)
    query_type = Column(String)

    # Cache management
    hit_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)  # Optional TTL

    def __repr__(self):
        return f"<QueryCache(query='{self.original_query[:50]}...', hits={self.hit_count})>"
