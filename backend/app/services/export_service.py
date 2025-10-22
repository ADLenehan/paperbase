"""
Export Service - Handle CSV, Excel, and JSON exports of extracted document data
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import pandas as pd
import io
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.document import Document, ExtractedField
from app.models.template import SchemaTemplate
from app.models.schema import Schema
import logging

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting document extraction data in various formats"""

    @staticmethod
    def build_export_query(
        db: Session,
        template_id: Optional[int] = None,
        schema_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        confidence_min: float = 0.0,
        verified_only: bool = False,
        status: Optional[str] = None,
        document_ids: Optional[List[int]] = None
    ):
        """Build a query for extracting documents based on filters"""

        # Start with base query joining documents and fields
        query = db.query(Document).join(
            ExtractedField,
            ExtractedField.document_id == Document.id
        )

        # Apply filters
        filters = []

        if template_id:
            # Filter by template (suggested_template_id for unprocessed, schema_id for processed)
            filters.append(
                or_(
                    Document.suggested_template_id == template_id,
                    Document.schema_id == template_id
                )
            )

        if schema_id:
            filters.append(Document.schema_id == schema_id)

        if date_from:
            filters.append(Document.uploaded_at >= datetime.combine(date_from, datetime.min.time()))

        if date_to:
            filters.append(Document.uploaded_at <= datetime.combine(date_to, datetime.max.time()))

        if status:
            filters.append(Document.status == status)

        if document_ids:
            filters.append(Document.id.in_(document_ids))

        if filters:
            query = query.filter(and_(*filters))

        # Apply field-level filters
        field_filters = []

        if confidence_min > 0:
            field_filters.append(ExtractedField.confidence_score >= confidence_min)

        if verified_only:
            field_filters.append(ExtractedField.verified == True)

        if field_filters:
            query = query.filter(and_(*field_filters))

        return query.distinct()

    @staticmethod
    def documents_to_records(documents: List[Document]) -> List[Dict[str, Any]]:
        """
        Convert documents with extracted fields to flat records

        Each document becomes one row with all extracted fields as columns
        """
        records = []

        for doc in documents:
            record = {
                "document_id": doc.id,
                "filename": doc.filename,
                "status": doc.status,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            }

            # Add extracted fields
            for field in doc.extracted_fields:
                # Use verified value if available, otherwise use extracted value
                value = field.verified_value if field.verified else field.field_value
                record[field.field_name] = value

                # Optionally add confidence scores as separate columns
                record[f"{field.field_name}_confidence"] = field.confidence_score
                record[f"{field.field_name}_verified"] = field.verified

            records.append(record)

        return records

    @staticmethod
    def documents_to_long_format(documents: List[Document]) -> List[Dict[str, Any]]:
        """
        Convert documents to long format (one row per field)

        Better for analysis and pivoting in Excel/BI tools
        """
        records = []

        for doc in documents:
            for field in doc.extracted_fields:
                record = {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "status": doc.status,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                    "field_name": field.field_name,
                    "extracted_value": field.field_value,
                    "verified_value": field.verified_value,
                    "final_value": field.verified_value if field.verified else field.field_value,
                    "confidence_score": field.confidence_score,
                    "verified": field.verified,
                    "verified_at": field.verified_at.isoformat() if field.verified_at else None,
                    "needs_verification": field.needs_verification,
                }
                records.append(record)

        return records

    @staticmethod
    def export_to_csv(
        records: List[Dict[str, Any]],
        include_metadata: bool = True
    ) -> bytes:
        """Export records to CSV format"""

        if not records:
            # Return empty CSV with headers
            df = pd.DataFrame(columns=["document_id", "filename", "status"])
        else:
            df = pd.DataFrame(records)

            # Optionally remove metadata columns
            if not include_metadata:
                metadata_cols = [col for col in df.columns if col.endswith(('_confidence', '_verified'))]
                df = df.drop(columns=metadata_cols, errors='ignore')

        # Convert to CSV bytes
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue().encode('utf-8')

    @staticmethod
    def export_to_excel(
        records: List[Dict[str, Any]],
        include_metadata: bool = True,
        sheet_name: str = "Extracted Data"
    ) -> bytes:
        """Export records to Excel format with formatting"""

        if not records:
            df = pd.DataFrame(columns=["document_id", "filename", "status"])
        else:
            df = pd.DataFrame(records)

            if not include_metadata:
                metadata_cols = [col for col in df.columns if col.endswith(('_confidence', '_verified'))]
                df = df.drop(columns=metadata_cols, errors='ignore')

        # Create Excel file in memory
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            # Get the worksheet to apply formatting
            worksheet = writer.sheets[sheet_name]

            # Auto-adjust column widths
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)  # Cap at 50
                worksheet.column_dimensions[column_letter].width = adjusted_width

            # Bold headers
            for cell in worksheet[1]:
                cell.font = cell.font.copy(bold=True)

        output.seek(0)
        return output.read()

    @staticmethod
    def export_to_json(
        records: List[Dict[str, Any]],
        format_type: str = "array"
    ) -> str:
        """
        Export records to JSON format

        format_type options:
        - "array": Standard JSON array
        - "records": One JSON object per line (JSON Lines)
        - "pretty": Formatted with indentation
        """

        if format_type == "records":
            # JSON Lines format (one object per line)
            return "\n".join(json.dumps(record) for record in records)
        elif format_type == "pretty":
            return json.dumps(records, indent=2)
        else:
            # Standard compact JSON array
            return json.dumps(records)

    @staticmethod
    def get_export_summary(
        db: Session,
        template_id: Optional[int] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None
    ) -> Dict[str, Any]:
        """Get summary statistics for export"""

        # Build query
        query = db.query(Document)

        if template_id:
            query = query.filter(
                or_(
                    Document.suggested_template_id == template_id,
                    Document.schema_id == template_id
                )
            )

        if date_from:
            query = query.filter(Document.uploaded_at >= datetime.combine(date_from, datetime.min.time()))

        if date_to:
            query = query.filter(Document.uploaded_at <= datetime.combine(date_to, datetime.max.time()))

        documents = query.all()

        # Calculate statistics
        total_docs = len(documents)
        total_fields = sum(len(doc.extracted_fields) for doc in documents)
        verified_fields = sum(
            sum(1 for field in doc.extracted_fields if field.verified)
            for doc in documents
        )

        avg_confidence = 0
        if total_fields > 0:
            total_confidence = sum(
                sum(field.confidence_score or 0 for field in doc.extracted_fields)
                for doc in documents
            )
            avg_confidence = total_confidence / total_fields

        return {
            "total_documents": total_docs,
            "total_fields": total_fields,
            "verified_fields": verified_fields,
            "verification_rate": verified_fields / total_fields if total_fields > 0 else 0,
            "average_confidence": avg_confidence,
            "date_range": {
                "from": date_from.isoformat() if date_from else None,
                "to": date_to.isoformat() if date_to else None
            }
        }

    @staticmethod
    def export_by_template(
        db: Session,
        template_id: int,
        format: str = "excel",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        **kwargs
    ) -> bytes:
        """
        Convenience method to export all documents for a specific template
        """

        # Get template details
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
        if not template:
            raise ValueError(f"Template {template_id} not found")

        # Build query
        query = ExportService.build_export_query(
            db=db,
            template_id=template_id,
            date_from=date_from,
            date_to=date_to,
            **kwargs
        )

        documents = query.all()

        # Convert to records (wide format by default)
        records = ExportService.documents_to_records(documents)

        # Export in requested format
        if format.lower() == "csv":
            return ExportService.export_to_csv(records)
        elif format.lower() == "excel":
            return ExportService.export_to_excel(
                records,
                sheet_name=template.name[:31]  # Excel sheet name limit
            )
        elif format.lower() == "json":
            json_str = ExportService.export_to_json(records, format_type="pretty")
            return json_str.encode('utf-8')
        else:
            raise ValueError(f"Unsupported format: {format}")
