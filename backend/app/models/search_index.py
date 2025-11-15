"""
PostgreSQL models for document search index and template signatures.
These replace the Elasticsearch indexes.
"""
from datetime import datetime

from sqlalchemy import (
    JSON,
    ARRAY,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class DocumentSearchIndex(Base):
    """
    Full-text search index for documents.
    Replaces Elasticsearch 'documents' index.
    
    Uses PostgreSQL tsvector for full-text search and JSONB for dynamic fields.
    """
    __tablename__ = "document_search_index"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, unique=True)

    full_text = Column(Text)
    full_text_tsv = Column(TSVECTOR)  # Generated column in migration

    extracted_fields = Column(JSONB, nullable=False, default={})

    query_context = Column(JSONB, nullable=False, default={})  # template_name, field_names, canonical_fields, etc.
    all_text = Column(Text)  # Combined searchable text
    all_text_tsv = Column(TSVECTOR)  # Generated column in migration
    field_index = Column(ARRAY(String))  # Array of field names for discovery

    confidence_metrics = Column(JSONB, nullable=False, default={})  # min, max, avg, field_count, verified_count

    citation_metadata = Column(JSONB, nullable=False, default={})  # low_confidence_fields, audit_urls

    field_metadata = Column(JSONB, nullable=False, default={})  # field_name -> {description, aliases, hints, confidence, verified}

    # Timestamps
    indexed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    document = relationship("Document", backref="search_index")

    __table_args__ = (
        Index('idx_document_search_fulltext', 'full_text_tsv', postgresql_using='gin'),
        Index('idx_document_search_alltext', 'all_text_tsv', postgresql_using='gin'),
        Index('idx_document_search_extracted_fields', 'extracted_fields', postgresql_using='gin'),
        Index('idx_document_search_query_context', 'query_context', postgresql_using='gin'),
        Index('idx_document_search_field_index', 'field_index', postgresql_using='gin'),
    )


class TemplateSignature(Base):
    """
    Template signatures for similarity matching.
    Replaces Elasticsearch 'template_signatures' index.
    
    Uses PostgreSQL tsvector for full-text search and pg_trgm for similarity.
    """
    __tablename__ = "template_signatures"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("schemas.id", ondelete="CASCADE"), nullable=False, unique=True)
    template_name = Column(String(255), nullable=False)

    field_names = Column(ARRAY(String), nullable=False)  # Array of field names
    field_names_text = Column(Text)  # Space-separated for text search
    field_names_tsv = Column(TSVECTOR)  # Generated column in migration

    sample_text = Column(Text)
    sample_text_tsv = Column(TSVECTOR)  # Generated column in migration

    category = Column(String(100))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    schema = relationship("Schema", backref="signature")

    __table_args__ = (
        Index('idx_template_sig_field_names', 'field_names_tsv', postgresql_using='gin'),
        Index('idx_template_sig_sample_text', 'sample_text_tsv', postgresql_using='gin'),
        Index('idx_template_sig_field_names_trgm', 'field_names_text', postgresql_using='gin', postgresql_ops={'field_names_text': 'gin_trgm_ops'}),
        Index('idx_template_sig_sample_text_trgm', 'sample_text', postgresql_using='gin', postgresql_ops={'sample_text': 'gin_trgm_ops'}),
    )
