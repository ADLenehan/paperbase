# Feature Documentation

This folder contains detailed documentation for all major features and implementations in Paperbase.

**Total Features Documented**: 40 documents

## 📑 Quick Navigation

### By Feature Area
- [Search & Query](#search--query-features) - Natural language search, query suggestions, aggregations
- [Document Processing](#document-processing--extraction) - Extraction, tables, complex data types
- [Audit & Quality](#audit--quality-control) - HITL review, confidence scoring, UX improvements
- [Multi-Template System](#multi-template--folder-organization) - Template matching, folder views, hybrid approach
- [Authentication & Permissions](#authentication--permissions) - RBAC, JWT, API keys
- [Settings & Configuration](#settings--configuration) - Hierarchical settings, thresholds
- [Infrastructure](#infrastructure--optimization) - Elasticsearch, pipeline optimization, indexing
- [Export & Sharing](#export--sharing) - Data export, chat folders
- [Implementation Summaries](#implementation--milestone-summaries) - Project status, completion reports

---

## Search & Query Features

### Natural Language Search
- **[NL Query Guide](NL_QUERY_GUIDE.md)** - User guide for natural language search
- **[NL Query Implementation](NL_QUERY_IMPLEMENTATION.md)** - Technical implementation details
- **[NL Query Summary](NL_QUERY_SUMMARY.md)** - Feature summary and architecture
- **[NL Search Implementation Complete](NL_SEARCH_IMPLEMENTATION_COMPLETE.md)** - Completion report
- **[NL Search Optimization](NL_SEARCH_OPTIMIZATION.md)** - Performance optimizations
- **[NL Search Quick Start](NL_SEARCH_QUICK_START.md)** - Quick setup guide

### Search Features
- **[Query Suggestions](QUERY_SUGGESTIONS_FEATURE.md)** - AI-powered search suggestions
- **[Query Field Lineage](QUERY_FIELD_LINEAGE_IMPLEMENTATION.md)** - Track which fields are used in queries
- **[Search Aggregation](SEARCH_AGGREGATION_IMPLEMENTATION.md)** - Faceted search and aggregations
- **[Chat Folder Search](CHAT_FOLDER_SEARCH.md)** - Search within chat conversations

---

## Document Processing & Extraction

### Complex Data Extraction
- **[Complex Table Extraction](COMPLEX_TABLE_EXTRACTION.md)** - Advanced table parsing with arrays and nested objects
- **[Complex Data Implementation Status](COMPLEX_DATA_IMPLEMENTATION_STATUS.md)** - Current implementation state
- **[Extraction Preview Feature](EXTRACTION_PREVIEW_FEATURE.md)** - Preview extraction results before indexing

### Pipeline & Processing
- **[Pipeline Optimization](PIPELINE_OPTIMIZATION.md)** - Reducto `jobid://` reuse for 60% cost savings
- **[Pipeline Implementation Summary](PIPELINE_IMPLEMENTATION_SUMMARY.md)** - Implementation details
- **[Hybrid Matching Implementation](HYBRID_MATCHING_IMPLEMENTATION.md)** - Template matching strategy

---

## Audit & Quality Control

### Audit Interface
- **[Audit Tab Implementation](AUDIT_TAB_IMPLEMENTATION.md)** - Primary HITL audit interface
- **[Audit UX Improvements](AUDIT_UX_IMPROVEMENTS.md)** - User experience enhancements
- **[Low Confidence Audit Links](LOW_CONFIDENCE_AUDIT_LINKS.md)** - Deep-linking to low-confidence fields
- **[Low Confidence Audit Links Implementation](LOW_CONFIDENCE_AUDIT_LINKS_IMPLEMENTATION.md)** - Technical details

### Citations & UX
- **[UX and Citation Improvements](UX_AND_CITATION_IMPROVEMENTS.md)** - Enhanced citations, PDF viewer, badges

---

## Multi-Template & Folder Organization

- **[Multi Template Quick Start](MULTI_TEMPLATE_QUICKSTART.md)** - Quick start guide
- **[Multi Template Ready](MULTI_TEMPLATE_READY.md)** - Feature readiness report
- **[Folder View Update](FOLDER_VIEW_UPDATE.md)** - Virtual folder organization by template

---

## Authentication & Permissions

- **[Permissions Architecture](PERMISSIONS_ARCHITECTURE.md)** - RBAC system design
- **[Permissions Implementation Status](PERMISSIONS_IMPLEMENTATION_STATUS.md)** - Current implementation state
- **[Permissions Quick Start](PERMISSIONS_QUICKSTART.md)** - Quick setup guide
- **[Permissions Summary](PERMISSIONS_SUMMARY.md)** - Feature overview

---

## Settings & Configuration

- **[Settings Implementation](SETTINGS_IMPLEMENTATION.md)** - Hierarchical settings system
- **[Settings Consolidation](SETTINGS_CONSOLIDATION.md)** - Settings organization and cleanup

---

## Infrastructure & Optimization

### Elasticsearch
- **[Elasticsearch Mapping Improvements](ELASTICSEARCH_MAPPING_IMPROVEMENTS.md)** - Production-ready strict mappings
- **[Smart Indexing Guide](SMART_INDEXING_GUIDE.md)** - Intelligent indexing strategies
- **[Smart Indexing Summary](SMART_INDEXING_SUMMARY.md)** - Implementation overview
- **[Vector Search Quick Start](VECTOR_SEARCH_QUICKSTART.md)** - Vector/semantic search setup

### Performance
- **[Final Optimizations](FINAL_OPTIMIZATIONS.md)** - System-wide performance improvements

---

## Export & Sharing

- **[Export Feature](EXPORT_FEATURE.md)** - Document and data export functionality
- **[Export Implementation Summary](EXPORT_IMPLEMENTATION_SUMMARY.md)** - Implementation details

---

## Implementation & Milestone Summaries

- **[Implementation Complete](IMPLEMENTATION_COMPLETE.md)** - Major feature completion report
- **[Implementation Summary](IMPLEMENTATION_SUMMARY.md)** - Overall implementation status

---

## Feature Status Overview

### ✅ Production Ready
- Pipeline Optimization (jobid:// reuse)
- Elasticsearch Mappings (strict mode)
- Permissions & Authentication (backend complete)
- Audit Links & PDF deep-linking
- Query Field Lineage
- Natural Language Search
- Multi-Template System
- Settings Management

### 🚧 In Development
- Complex Table Extraction (backend ready, frontend pending)
- Extraction Preview (integration pending)
- Query Suggestions (testing phase)
- Vector Search (experimental)

### 📋 Planned
- See [PROJECT_PLAN.md](../../PROJECT_PLAN.md) for complete roadmap

---

## Quick Links

- **[Main Project Instructions](../../CLAUDE.md)** - Project overview and development guide
- **[Architecture Document](../../NEW_ARCHITECTURE.md)** - System architecture details
- **[Project Plan](../../PROJECT_PLAN.md)** - Feature roadmap and TODOs
- **[API Documentation](../API_DOCUMENTATION.md)** - API reference
- **[Deployment Guide](../DEPLOYMENT.md)** - Production deployment
- **[Testing Guide](../TESTING_GUIDE.md)** - Testing strategies
- **[User Guide](../USER_GUIDE.md)** - End-user documentation

---

**Last Updated**: 2025-11-02
**Total Features**: 40 documented features and implementations
