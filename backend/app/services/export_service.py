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
                # Handle complex data types (array, table, array_of_objects)
                if field.field_type in ["array", "table", "array_of_objects"]:
                    # Complex fields use field_value_json
                    if field.verified and field.verified_value_json:
                        value = field.verified_value_json
                    else:
                        value = field.field_value_json
                else:
                    # Simple fields use field_value
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
                # Handle complex vs simple field types
                if field.field_type in ["array", "table", "array_of_objects"]:
                    extracted_value = field.field_value_json
                    verified_value = field.verified_value_json
                    final_value = verified_value if field.verified else extracted_value
                else:
                    extracted_value = field.field_value
                    verified_value = field.verified_value
                    final_value = verified_value if field.verified else extracted_value

                record = {
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "status": doc.status,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                    "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                    "field_name": field.field_name,
                    "field_type": field.field_type or "text",  # Include field type
                    "extracted_value": extracted_value,
                    "verified_value": verified_value,
                    "final_value": final_value,
                    "confidence_score": field.confidence_score,
                    "verified": field.verified,
                    "verified_at": field.verified_at.isoformat() if field.verified_at else None,
                    "needs_verification": field.needs_verification,
                }
                records.append(record)

        return records

    @staticmethod
    def _detect_complex_fields(documents: List[Document]) -> Dict[str, List[str]]:
        """
        Analyze documents to detect complex field types

        Returns:
            Dict with field types as keys and field names as values:
            {
                "array": ["colors", "tags"],
                "table": ["grading_table"],
                "array_of_objects": ["line_items"]
            }
        """
        complex_fields = {
            "array": set(),
            "table": set(),
            "array_of_objects": set()
        }

        for doc in documents:
            for field in doc.extracted_fields:
                if field.field_type in ["array", "table", "array_of_objects"]:
                    complex_fields[field.field_type].add(field.field_name)

        # Convert sets to lists
        return {
            field_type: sorted(list(field_names))
            for field_type, field_names in complex_fields.items()
        }

    @staticmethod
    def _serialize_complex_field(
        field: ExtractedField,
        format_type: str,
        include_verified: bool = True
    ) -> Any:
        """
        Serialize complex field based on export format

        Args:
            field: ExtractedField with complex data type
            format_type: "csv", "excel", or "json"
            include_verified: Whether to use verified value if available

        Returns:
            Serialized value appropriate for the format
        """
        # Get the value (verified or extracted)
        if include_verified and field.verified and field.verified_value_json:
            value = field.verified_value_json
        elif field.field_value_json:
            value = field.field_value_json
        else:
            return None

        # Handle None values
        if value is None:
            return None

        # Format-specific serialization
        if format_type == "json":
            # JSON preserves full structure
            return value

        elif field.field_type == "array":
            # Arrays: comma-separated string for CSV/Excel
            if isinstance(value, list):
                return ", ".join(str(item) for item in value)
            return str(value)

        elif field.field_type in ["table", "array_of_objects"]:
            # Tables and array_of_objects: JSON string for CSV/Excel
            # (will be expanded to separate sheets for Excel if expand_complex_fields=True)
            return json.dumps(value)

        else:
            # Fallback: JSON string
            return json.dumps(value)

    @staticmethod
    def _create_table_sheet(
        documents: List[Document],
        field_name: str
    ) -> pd.DataFrame:
        """
        Create DataFrame for a table field (for Excel multi-sheet export)

        Args:
            documents: List of documents containing the table field
            field_name: Name of the table field to extract

        Returns:
            DataFrame with columns: document_id, filename, [table columns...]
        """
        rows = []

        for doc in documents:
            for field in doc.extracted_fields:
                if field.field_name != field_name or field.field_type != "table":
                    continue

                # Get table data (verified or extracted)
                table_data = None
                if field.verified and field.verified_value_json:
                    table_data = field.verified_value_json
                elif field.field_value_json:
                    table_data = field.field_value_json

                if not table_data or not isinstance(table_data, dict):
                    continue

                # Extract rows from table structure
                table_rows = table_data.get("rows", [])
                if not isinstance(table_rows, list):
                    continue

                # Each table row becomes a row in the sheet
                for table_row in table_rows:
                    if not isinstance(table_row, dict):
                        continue

                    row = {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        **table_row  # Spread table columns
                    }
                    rows.append(row)

        if not rows:
            # Return empty DataFrame with minimal columns
            return pd.DataFrame(columns=["document_id", "filename"])

        return pd.DataFrame(rows)

    @staticmethod
    def _create_array_of_objects_sheet(
        documents: List[Document],
        field_name: str
    ) -> pd.DataFrame:
        """
        Create DataFrame for an array_of_objects field (for Excel multi-sheet export)

        Args:
            documents: List of documents containing the array_of_objects field
            field_name: Name of the array_of_objects field to extract

        Returns:
            DataFrame with columns: document_id, filename, [object properties...]
        """
        rows = []

        for doc in documents:
            for field in doc.extracted_fields:
                if field.field_name != field_name or field.field_type != "array_of_objects":
                    continue

                # Get array data (verified or extracted)
                array_data = None
                if field.verified and field.verified_value_json:
                    array_data = field.verified_value_json
                elif field.field_value_json:
                    array_data = field.field_value_json

                if not array_data or not isinstance(array_data, list):
                    continue

                # Each array item becomes a row in the sheet
                for item in array_data:
                    if not isinstance(item, dict):
                        continue

                    row = {
                        "document_id": doc.id,
                        "filename": doc.filename,
                        **item  # Spread object properties
                    }
                    rows.append(row)

        if not rows:
            # Return empty DataFrame with minimal columns
            return pd.DataFrame(columns=["document_id", "filename"])

        return pd.DataFrame(rows)

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
        sheet_name: str = "Extracted Data",
        documents: Optional[List[Document]] = None,
        expand_complex_fields: bool = True
    ) -> bytes:
        """
        Export records to Excel format with formatting

        Args:
            records: List of document records
            include_metadata: Include confidence and verification columns
            sheet_name: Name for the main sheet
            documents: Original documents (needed for complex field expansion)
            expand_complex_fields: Create separate sheets for table/array_of_objects fields

        Returns:
            Excel file bytes
        """

        if not records:
            df = pd.DataFrame(columns=["document_id", "filename", "status"])
        else:
            df = pd.DataFrame(records)

            # Serialize complex fields for the main sheet
            for col in df.columns:
                # Check if this column contains complex data (lists, dicts)
                if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
                    # Convert to JSON string for main sheet display
                    df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x)

            if not include_metadata:
                metadata_cols = [col for col in df.columns if col.endswith(('_confidence', '_verified'))]
                df = df.drop(columns=metadata_cols, errors='ignore')

        # Create Excel file in memory
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Write main sheet
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

            # Create additional sheets for complex fields if requested
            if expand_complex_fields and documents:
                complex_fields = ExportService._detect_complex_fields(documents)

                # Create sheet for each table field
                for table_field in complex_fields.get("table", []):
                    table_df = ExportService._create_table_sheet(documents, table_field)
                    if not table_df.empty:
                        # Sanitize sheet name (Excel limit: 31 chars, no special chars)
                        sheet_name_clean = table_field[:31].replace('/', '_').replace('\\', '_')
                        table_df.to_excel(writer, sheet_name=f"{sheet_name_clean}_table", index=False)

                        # Apply formatting to table sheet
                        if f"{sheet_name_clean}_table" in writer.sheets:
                            table_ws = writer.sheets[f"{sheet_name_clean}_table"]
                            for cell in table_ws[1]:
                                cell.font = cell.font.copy(bold=True)

                # Create sheet for each array_of_objects field
                for array_field in complex_fields.get("array_of_objects", []):
                    array_df = ExportService._create_array_of_objects_sheet(documents, array_field)
                    if not array_df.empty:
                        # Sanitize sheet name
                        sheet_name_clean = array_field[:31].replace('/', '_').replace('\\', '_')
                        array_df.to_excel(writer, sheet_name=f"{sheet_name_clean}_items", index=False)

                        # Apply formatting to array sheet
                        if f"{sheet_name_clean}_items" in writer.sheets:
                            array_ws = writer.sheets[f"{sheet_name_clean}_items"]
                            for cell in array_ws[1]:
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
        """Get summary statistics for export using efficient database aggregations"""
        from sqlalchemy import func, case

        doc_query = db.query(Document.id)

        if template_id:
            doc_query = doc_query.filter(
                or_(
                    Document.suggested_template_id == template_id,
                    Document.schema_id == template_id
                )
            )

        if date_from:
            doc_query = doc_query.filter(Document.uploaded_at >= datetime.combine(date_from, datetime.min.time()))

        if date_to:
            doc_query = doc_query.filter(Document.uploaded_at <= datetime.combine(date_to, datetime.max.time()))

        total_docs = doc_query.count()

        # Calculate field statistics using a single aggregation query
        field_stats = db.query(
            func.count(ExtractedField.id).label('total_fields'),
            func.sum(case((ExtractedField.verified == True, 1), else_=0)).label('verified_fields'),
            func.avg(ExtractedField.confidence_score).label('avg_confidence')
        ).join(
            Document,
            ExtractedField.document_id == Document.id
        ).filter(
            Document.id.in_(doc_query.subquery())
        ).first()

        # Extract results with safe defaults
        total_fields = field_stats.total_fields or 0
        verified_fields = field_stats.verified_fields or 0
        avg_confidence = float(field_stats.avg_confidence) if field_stats.avg_confidence else 0.0

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
        expand_complex_fields: bool = True,
        **kwargs
    ) -> bytes:
        """
        Convenience method to export all documents for a specific template

        Args:
            db: Database session
            template_id: Template ID to export
            format: Export format ("excel", "csv", or "json")
            date_from: Start date filter
            date_to: End date filter
            expand_complex_fields: For Excel, create separate sheets for tables/arrays
            **kwargs: Additional filters (confidence_min, verified_only, etc.)

        Returns:
            Export file bytes
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
                sheet_name=template.name[:31],  # Excel sheet name limit
                documents=documents,  # Pass documents for complex field expansion
                expand_complex_fields=expand_complex_fields
            )
        elif format.lower() == "json":
            json_str = ExportService.export_to_json(records, format_type="pretty")
            return json_str.encode('utf-8')
        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def analyze_template_compatibility(
        db: Session,
        template_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Analyze compatibility between multiple templates for export

        Determines whether templates can be merged into a single export
        or should be separated based on field overlap.

        Args:
            db: Database session
            template_ids: List of template IDs to analyze

        Returns:
            Dict with analysis results:
            {
                "strategy": "merged" | "separated",
                "field_overlap": 0.85,
                "common_fields": ["invoice_number", "date"],
                "unique_fields": {"template_1": ["field_a"], "template_2": ["field_b"]},
                "has_complex_fields": True,
                "complex_field_types": ["table", "array_of_objects"],
                "recommended_format": "excel",
                "warning": "Optional warning message"
            }
        """
        # Fetch templates
        templates = db.query(SchemaTemplate).filter(
            SchemaTemplate.id.in_(template_ids)
        ).all()

        if len(templates) != len(template_ids):
            raise ValueError("One or more template IDs not found")

        if len(templates) == 1:
            # Single template - simple case
            template = templates[0]
            field_names = [f.get("name") for f in template.fields] if template.fields else []

            # Check for complex fields
            complex_types = set()
            for field in template.fields or []:
                if field.get("type") in ["array", "table", "array_of_objects"]:
                    complex_types.add(field.get("type"))

            return {
                "strategy": "single_template",
                "template_id": template.id,
                "template_name": template.name,
                "field_count": len(field_names),
                "has_complex_fields": len(complex_types) > 0,
                "complex_field_types": sorted(list(complex_types)),
                "recommended_format": "excel" if complex_types else "csv"
            }

        # Multiple templates - analyze compatibility
        template_fields = {}
        all_fields = set()
        complex_types = set()

        for template in templates:
            field_names = set()
            for field in template.fields or []:
                field_name = field.get("name")
                field_type = field.get("type", "text")

                field_names.add(field_name)
                all_fields.add(field_name)

                if field_type in ["array", "table", "array_of_objects"]:
                    complex_types.add(field_type)

            template_fields[template.id] = {
                "name": template.name,
                "fields": field_names
            }

        # Calculate field overlap
        if not all_fields:
            field_overlap = 1.0
            common_fields = set()
        else:
            # Find common fields across all templates
            common_fields = set.intersection(
                *[data["fields"] for data in template_fields.values()]
            )
            field_overlap = len(common_fields) / len(all_fields)

        # Determine strategy
        # If >80% overlap, merge is reasonable
        # If <80% overlap, separate sheets/files recommended
        strategy = "merged" if field_overlap >= 0.8 else "separated"

        # Find unique fields per template
        unique_fields = {}
        for template_id, data in template_fields.items():
            unique = data["fields"] - common_fields
            if unique:
                unique_fields[data["name"]] = sorted(list(unique))

        # Recommendation
        recommended_format = "excel"  # Excel handles both strategies well
        warning = None

        if strategy == "separated" and len(templates) > 5:
            warning = "Exporting many templates with different schemas. Consider filtering to specific templates."

        if complex_types and "csv" in str(recommended_format):
            warning = "Complex fields detected. Excel format recommended for best results."

        return {
            "strategy": strategy,
            "field_overlap": round(field_overlap, 2),
            "common_fields": sorted(list(common_fields)),
            "unique_fields": unique_fields,
            "template_count": len(templates),
            "total_fields": len(all_fields),
            "has_complex_fields": len(complex_types) > 0,
            "complex_field_types": sorted(list(complex_types)),
            "recommended_format": recommended_format,
            "warning": warning
        }

    @staticmethod
    def export_multi_template_merged(
        db: Session,
        template_ids: List[int],
        format: str = "excel",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        expand_complex_fields: bool = True,
        **kwargs
    ) -> bytes:
        """
        Export documents from multiple templates merged into a single file

        Creates union of all fields with template_name column to identify source.
        Best for templates with high field overlap (>80%).

        Args:
            db: Database session
            template_ids: List of template IDs to export
            format: Export format
            date_from: Start date filter
            date_to: End date filter
            expand_complex_fields: For Excel, create separate sheets
            **kwargs: Additional filters

        Returns:
            Export file bytes
        """
        # Get all documents from all templates
        all_documents = []
        template_map = {}

        for template_id in template_ids:
            query = ExportService.build_export_query(
                db=db,
                template_id=template_id,
                date_from=date_from,
                date_to=date_to,
                **kwargs
            )
            docs = query.all()
            all_documents.extend(docs)

            # Store template info for labeling
            template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
            if template:
                template_map[template_id] = template.name

        # Convert to records
        records = []
        for doc in all_documents:
            record = {
                "document_id": doc.id,
                "template_name": template_map.get(doc.schema_id, "Unknown"),
                "template_id": doc.schema_id,
                "filename": doc.filename,
                "status": doc.status,
                "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
            }

            # Add extracted fields
            for field in doc.extracted_fields:
                if field.field_type in ["array", "table", "array_of_objects"]:
                    if field.verified and field.verified_value_json:
                        value = field.verified_value_json
                    else:
                        value = field.field_value_json
                else:
                    value = field.verified_value if field.verified else field.field_value

                record[field.field_name] = value
                record[f"{field.field_name}_confidence"] = field.confidence_score
                record[f"{field.field_name}_verified"] = field.verified

            records.append(record)

        # Export in requested format
        if format.lower() == "csv":
            return ExportService.export_to_csv(records)
        elif format.lower() == "excel":
            return ExportService.export_to_excel(
                records,
                sheet_name="Merged Export",
                documents=all_documents,
                expand_complex_fields=expand_complex_fields
            )
        elif format.lower() == "json":
            json_str = ExportService.export_to_json(records, format_type="pretty")
            return json_str.encode('utf-8')
        else:
            raise ValueError(f"Unsupported format: {format}")

    @staticmethod
    def export_multi_template_separated(
        db: Session,
        template_ids: List[int],
        format: str = "excel",
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        expand_complex_fields: bool = True,
        **kwargs
    ) -> bytes:
        """
        Export documents from multiple templates into separated outputs

        For Excel: Creates one sheet per template
        For CSV: Would need to return ZIP (not yet implemented - returns merged for now)
        For JSON: Groups by template

        Args:
            db: Database session
            template_ids: List of template IDs to export
            format: Export format
            date_from: Start date filter
            date_to: End date filter
            expand_complex_fields: For Excel, create separate sheets for complex fields
            **kwargs: Additional filters

        Returns:
            Export file bytes
        """
        if format.lower() == "excel":
            # Create multi-sheet Excel with one sheet per template
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for template_id in template_ids:
                    # Get template
                    template = db.query(SchemaTemplate).filter(
                        SchemaTemplate.id == template_id
                    ).first()

                    if not template:
                        continue

                    # Get documents for this template
                    query = ExportService.build_export_query(
                        db=db,
                        template_id=template_id,
                        date_from=date_from,
                        date_to=date_to,
                        **kwargs
                    )
                    documents = query.all()

                    if not documents:
                        continue

                    # Convert to records
                    records = ExportService.documents_to_records(documents)

                    # Create DataFrame
                    df = pd.DataFrame(records)

                    # Serialize complex fields
                    for col in df.columns:
                        if df[col].apply(lambda x: isinstance(x, (list, dict))).any():
                            df[col] = df[col].apply(
                                lambda x: json.dumps(x) if isinstance(x, (list, dict)) else x
                            )

                    # Sanitize sheet name
                    sheet_name = template.name[:31].replace('/', '_').replace('\\', '_')

                    # Write to sheet
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

                    # Apply formatting
                    worksheet = writer.sheets[sheet_name]
                    for cell in worksheet[1]:
                        cell.font = cell.font.copy(bold=True)

                    # Create additional sheets for complex fields
                    if expand_complex_fields:
                        complex_fields = ExportService._detect_complex_fields(documents)

                        for table_field in complex_fields.get("table", []):
                            table_df = ExportService._create_table_sheet(documents, table_field)
                            if not table_df.empty:
                                table_sheet_name = f"{sheet_name[:25]}_{table_field[:5]}"
                                table_df.to_excel(writer, sheet_name=table_sheet_name, index=False)

                        for array_field in complex_fields.get("array_of_objects", []):
                            array_df = ExportService._create_array_of_objects_sheet(documents, array_field)
                            if not array_df.empty:
                                array_sheet_name = f"{sheet_name[:25]}_{array_field[:5]}"
                                array_df.to_excel(writer, sheet_name=array_sheet_name, index=False)

            output.seek(0)
            return output.read()

        elif format.lower() == "json":
            # Group by template in JSON
            result = {}

            for template_id in template_ids:
                template = db.query(SchemaTemplate).filter(
                    SchemaTemplate.id == template_id
                ).first()

                if not template:
                    continue

                query = ExportService.build_export_query(
                    db=db,
                    template_id=template_id,
                    date_from=date_from,
                    date_to=date_to,
                    **kwargs
                )
                documents = query.all()
                records = ExportService.documents_to_records(documents)

                result[template.name] = records

            return json.dumps(result, indent=2).encode('utf-8')

        else:
            # CSV: Fall back to merged export
            # TODO: Implement ZIP file with multiple CSVs
            logger.warning("CSV separated export not yet implemented, using merged export")
            return ExportService.export_multi_template_merged(
                db, template_ids, "csv", date_from, date_to, **kwargs
            )
