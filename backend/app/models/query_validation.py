"""
Query Validation Model

Tracks user feedback on query results to improve accuracy over time.
This enables a learning loop where successful queries strengthen patterns
and unsuccessful queries trigger refinements.
"""

from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Float, Integer, String, Text

from app.core.database import Base


class QueryValidation(Base):
    """
    Tracks user validation and feedback on search query results.

    When a user provides feedback on query results (helpful/not helpful,
    corrects a result, etc.), we store it here to:
    1. Learn which queries work well
    2. Identify patterns in successful queries
    3. Auto-generate query patterns for caching
    4. Improve field alias detection
    """
    __tablename__ = "query_validations"

    id = Column(Integer, primary_key=True, index=True)

    # Query information
    query_text = Column(String, nullable=False, index=True)
    query_hash = Column(String, index=True)  # Hash for exact match lookup
    query_type = Column(String, index=True)  # search, aggregate, filter, retrieve
    intent_detected = Column(String)  # Detected intent from QueryOptimizer

    # Query analysis
    optimization_used = Column(Boolean, default=False)  # True if QueryOptimizer used, False if Claude used
    confidence_score = Column(Float)  # Confidence from QueryOptimizer
    filters_extracted = Column(JSON)  # Filters that were extracted
    fields_queried = Column(JSON)  # Fields involved in the query

    # Elasticsearch query
    es_query = Column(JSON, nullable=False)  # The ES query that was executed

    # Results
    total_results = Column(Integer, default=0)
    result_ids = Column(JSON)  # IDs of documents returned (top 20)

    # User feedback
    feedback_type = Column(String, index=True)  # helpful, not_helpful, corrected, no_results
    feedback_score = Column(Float)  # 0.0-1.0 rating if provided
    user_comment = Column(Text)  # Optional text feedback

    # Corrections (if user modified the search)
    corrected_query = Column(String)  # If user reformulated the query
    clicked_result_id = Column(Integer)  # Which result did they click on?
    clicked_result_rank = Column(Integer)  # What position was it?

    # Context
    template_name = Column(String, index=True)  # If template-specific
    folder_path = Column(String)  # If folder-scoped
    conversation_context = Column(JSON)  # Previous queries in conversation

    # Success metrics
    was_successful = Column(Boolean, default=False)  # Overall success flag
    success_confidence = Column(Float, default=0.5)  # How confident we are in success

    # Pattern learning
    pattern_id = Column(Integer)  # Link to QueryPattern if one was generated
    contributed_to_pattern = Column(Boolean, default=False)  # Used for pattern learning

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    feedback_at = Column(DateTime)  # When feedback was provided

    # Session tracking
    session_id = Column(String, index=True)  # For grouping related queries
    user_id = Column(String, index=True)  # Future: multi-user support

    def __repr__(self):
        return (
            f"<QueryValidation(query='{self.query_text[:50]}...', "
            f"feedback='{self.feedback_type}', successful={self.was_successful})>"
        )


class QueryImprovement(Base):
    """
    Tracks improvements made to the query system based on validation data.

    This is the "learning" part - when we analyze QueryValidation data
    and make changes to improve accuracy.
    """
    __tablename__ = "query_improvements"

    id = Column(Integer, primary_key=True, index=True)

    # What was improved
    improvement_type = Column(String, nullable=False, index=True)
    # Types: field_alias, query_pattern, canonical_mapping, filter_extraction

    # Details
    description = Column(Text, nullable=False)  # Human-readable description

    # What changed
    before_config = Column(JSON)  # Configuration before change
    after_config = Column(JSON)  # Configuration after change

    # Impact
    affected_queries = Column(Integer, default=0)  # How many queries this should improve
    validation_ids = Column(JSON)  # QueryValidation IDs that triggered this

    # Performance tracking
    success_rate_before = Column(Float)  # Success rate before improvement
    success_rate_after = Column(Float)  # Success rate after (measured over time)

    # Status
    status = Column(String, default="proposed")  # proposed, applied, validated, rolled_back
    applied_at = Column(DateTime)
    validated_at = Column(DateTime)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="system")  # system or user_id

    def __repr__(self):
        return (
            f"<QueryImprovement(type='{self.improvement_type}', "
            f"status='{self.status}', affected={self.affected_queries})>"
        )


class FieldAliasLearning(Base):
    """
    Tracks learned field aliases from user queries and corrections.

    When users consistently refer to "invoice_total" as "amount" or "total",
    we learn these aliases and add them to the system.
    """
    __tablename__ = "field_alias_learning"

    id = Column(Integer, primary_key=True, index=True)

    # Field information
    actual_field_name = Column(String, nullable=False, index=True)
    canonical_category = Column(String, index=True)  # amount, date, entity_name, etc.

    # Learned alias
    alias_term = Column(String, nullable=False, index=True)

    # Evidence
    usage_count = Column(Integer, default=1)  # How many times seen
    success_count = Column(Integer, default=0)  # How many successful queries
    failure_count = Column(Integer, default=0)  # How many failed queries

    # Confidence
    confidence_score = Column(Float, default=0.5)
    # Calculated as: success_count / (success_count + failure_count + smoothing)

    # Source
    source = Column(String, default="user_query")  # user_query, schema_metadata, manual
    query_validations = Column(JSON)  # List of validation IDs that support this

    # Status
    status = Column(String, default="candidate")  # candidate, validated, applied, rejected
    applied_to_schema_registry = Column(Boolean, default=False)

    # Metadata
    first_seen = Column(DateTime, default=datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<FieldAliasLearning(field='{self.actual_field_name}', "
            f"alias='{self.alias_term}', confidence={self.confidence_score:.2f})>"
        )

    def update_confidence(self):
        """Recalculate confidence score based on success/failure counts."""
        total = self.success_count + self.failure_count
        if total > 0:
            # Bayesian smoothing with prior of 0.5
            self.confidence_score = (self.success_count + 1) / (total + 2)
        else:
            self.confidence_score = 0.5
