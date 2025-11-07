"""
Export API - Endpoints for exporting document data in various formats
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field
import io
import logging

from app.core.database import get_db
from app.services.export_service import ExportService
from app.models.template import SchemaTemplate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/export", tags=["export"])


class ExportRequest(BaseModel):
    """Request model for custom exports"""
    template_id: Optional[int] = Field(None, description="Single template ID (for backwards compatibility)")
    template_ids: Optional[List[int]] = Field(None, description="Multiple template IDs for multi-template export")
    document_ids: Optional[List[int]] = Field(None, description="Specific document IDs to export")
    date_from: Optional[date] = Field(None, description="Start date filter")
    date_to: Optional[date] = Field(None, description="End date filter")
    confidence_min: float = Field(0.0, ge=0.0, le=1.0, description="Minimum confidence score")
    verified_only: bool = Field(False, description="Only include verified fields")
    status: Optional[str] = Field(None, description="Filter by document status")
    include_metadata: bool = Field(True, description="Include confidence scores and verification status")
    format_type: str = Field("wide", description="wide (one row per doc) or long (one row per field)")
    expand_complex_fields: bool = Field(True, description="For Excel, create separate sheets for tables/arrays")


class AnalyzeTemplatesRequest(BaseModel):
    """Request model for analyzing template compatibility"""
    template_ids: List[int] = Field(..., description="List of template IDs to analyze")


@router.get("/templates")
async def list_exportable_templates(db: Session = Depends(get_db)):
    """
    Get list of templates with document counts for export selection
    """
    templates = db.query(SchemaTemplate).all()

    template_list = []
    for template in templates:
        # Count documents using this template
        from app.models.document import Document
        from sqlalchemy import or_

        doc_count = db.query(Document).filter(
            or_(
                Document.schema_id == template.id,
                Document.suggested_template_id == template.id
            )
        ).count()

        template_list.append({
            "id": template.id,
            "name": template.name,
            "category": template.category,
            "description": template.description,
            "icon": template.icon,
            "document_count": doc_count,
            "field_count": len(template.fields) if template.fields else 0
        })

    return {
        "templates": template_list,
        "total_templates": len(template_list)
    }


@router.get("/summary")
async def get_export_summary(
    template_id: Optional[int] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Get summary statistics for potential export
    Useful for showing preview before download
    """
    try:
        summary = ExportService.get_export_summary(
            db=db,
            template_id=template_id,
            date_from=date_from,
            date_to=date_to
        )

        # Add template info if specified
        if template_id:
            template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
            if template:
                summary["template"] = {
                    "id": template.id,
                    "name": template.name,
                    "category": template.category
                }

        return summary
    except Exception as e:
        logger.error(f"Error getting export summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-templates")
async def analyze_template_compatibility(
    request: AnalyzeTemplatesRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze compatibility between multiple templates for export

    Returns analysis including:
    - Recommended strategy (merged vs separated)
    - Field overlap percentage
    - Common and unique fields
    - Complex field detection
    - Format recommendations
    """
    try:
        analysis = ExportService.analyze_template_compatibility(
            db=db,
            template_ids=request.template_ids
        )

        return analysis

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template/{template_id}/csv")
async def export_template_csv(
    template_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    confidence_min: float = Query(0.0, ge=0.0, le=1.0),
    verified_only: bool = Query(False),
    include_metadata: bool = Query(True),
    db: Session = Depends(get_db)
):
    """
    Export all documents for a template as CSV
    """
    try:
        # Get template for filename
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Build query
        query = ExportService.build_export_query(
            db=db,
            template_id=template_id,
            date_from=date_from,
            date_to=date_to,
            confidence_min=confidence_min,
            verified_only=verified_only
        )

        documents = query.all()

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found matching criteria")

        # Convert to records and export
        records = ExportService.documents_to_records(documents)
        csv_data = ExportService.export_to_csv(records, include_metadata=include_metadata)

        # Generate filename
        filename = f"{template.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"

        return Response(
            content=csv_data,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template/{template_id}/excel")
async def export_template_excel(
    template_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    confidence_min: float = Query(0.0, ge=0.0, le=1.0),
    verified_only: bool = Query(False),
    include_metadata: bool = Query(True),
    expand_complex_fields: bool = Query(True, description="Create separate sheets for tables/arrays"),
    db: Session = Depends(get_db)
):
    """
    Export all documents for a template as Excel file with formatting

    If expand_complex_fields=true (default), creates separate sheets for:
    - Table fields (e.g., grading_table)
    - Array of objects fields (e.g., line_items)
    """
    try:
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        query = ExportService.build_export_query(
            db=db,
            template_id=template_id,
            date_from=date_from,
            date_to=date_to,
            confidence_min=confidence_min,
            verified_only=verified_only
        )

        documents = query.all()

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found matching criteria")

        records = ExportService.documents_to_records(documents)
        excel_data = ExportService.export_to_excel(
            records,
            include_metadata=include_metadata,
            sheet_name=template.name[:31],  # Excel sheet name limit
            documents=documents,  # Pass documents for complex field expansion
            expand_complex_fields=expand_complex_fields
        )

        filename = f"{template.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"

        return Response(
            content=excel_data,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting Excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/template/{template_id}/json")
async def export_template_json(
    template_id: int,
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    confidence_min: float = Query(0.0, ge=0.0, le=1.0),
    verified_only: bool = Query(False),
    format_type: str = Query("pretty", description="pretty, compact, or records (JSON Lines)"),
    db: Session = Depends(get_db)
):
    """
    Export all documents for a template as JSON

    Format types:
    - pretty: Formatted with indentation (human-readable)
    - compact: Minified JSON (smaller file size)
    - records: JSON Lines format (one object per line)
    """
    try:
        template = db.query(SchemaTemplate).filter(SchemaTemplate.id == template_id).first()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        query = ExportService.build_export_query(
            db=db,
            template_id=template_id,
            date_from=date_from,
            date_to=date_to,
            confidence_min=confidence_min,
            verified_only=verified_only
        )

        documents = query.all()

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found matching criteria")

        records = ExportService.documents_to_records(documents)
        json_data = ExportService.export_to_json(records, format_type=format_type)

        filename = f"{template.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.json"

        return Response(
            content=json_data,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting JSON: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/custom")
async def export_custom(
    request: ExportRequest,
    format: str = Query("excel", description="csv, excel, or json"),
    db: Session = Depends(get_db)
):
    """
    Custom export with advanced filtering options

    Supports:
    - Single template export (template_id)
    - Multi-template export (template_ids) with automatic merge/separate strategy
    - Specific document export (document_ids)
    - Complex field expansion for Excel (expand_complex_fields)
    - Date ranges, confidence filtering, verification status
    """
    try:
        # Handle multi-template export
        if request.template_ids and len(request.template_ids) > 0:
            # Analyze template compatibility
            analysis = ExportService.analyze_template_compatibility(
                db=db,
                template_ids=request.template_ids
            )

            # Use recommended strategy
            if analysis["strategy"] == "merged" or len(request.template_ids) == 1:
                data = ExportService.export_multi_template_merged(
                    db=db,
                    template_ids=request.template_ids,
                    format=format,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    expand_complex_fields=request.expand_complex_fields,
                    confidence_min=request.confidence_min,
                    verified_only=request.verified_only,
                    status=request.status
                )
            else:
                data = ExportService.export_multi_template_separated(
                    db=db,
                    template_ids=request.template_ids,
                    format=format,
                    date_from=request.date_from,
                    date_to=request.date_to,
                    expand_complex_fields=request.expand_complex_fields,
                    confidence_min=request.confidence_min,
                    verified_only=request.verified_only,
                    status=request.status
                )

            # Determine media type and extension
            if format == "csv":
                media_type = "text/csv"
                extension = "csv"
            elif format == "excel":
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                extension = "xlsx"
            else:
                media_type = "application/json"
                extension = "json"

            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

            return Response(
                content=data,
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename={filename}"}
            )

        # Single template or document-specific export
        query = ExportService.build_export_query(
            db=db,
            template_id=request.template_id,
            document_ids=request.document_ids,
            date_from=request.date_from,
            date_to=request.date_to,
            confidence_min=request.confidence_min,
            verified_only=request.verified_only,
            status=request.status
        )

        documents = query.all()

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found matching criteria")

        # Convert to records (wide or long format)
        if request.format_type == "long":
            records = ExportService.documents_to_long_format(documents)
        else:
            records = ExportService.documents_to_records(documents)

        # Export in requested format
        if format == "csv":
            data = ExportService.export_to_csv(records, include_metadata=request.include_metadata)
            media_type = "text/csv"
            extension = "csv"
        elif format == "excel":
            data = ExportService.export_to_excel(
                records,
                include_metadata=request.include_metadata,
                documents=documents,  # Pass documents for complex field expansion
                expand_complex_fields=request.expand_complex_fields
            )
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            extension = "xlsx"
        elif format == "json":
            json_str = ExportService.export_to_json(records, format_type="pretty")
            data = json_str.encode('utf-8')
            media_type = "application/json"
            extension = "json"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

        filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in custom export: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents")
async def export_documents(
    document_ids: str = Query(..., description="Comma-separated document IDs"),
    format: str = Query("excel", description="csv, excel, or json"),
    include_metadata: bool = Query(True),
    expand_complex_fields: bool = Query(True, description="Create separate sheets for tables/arrays"),
    db: Session = Depends(get_db)
):
    """
    Export specific documents by ID

    Useful for exporting selected documents from the UI.
    Supports complex field expansion for Excel exports (default: true).
    """
    try:
        # Parse document IDs
        doc_id_list = [int(x.strip()) for x in document_ids.split(",")]

        query = ExportService.build_export_query(
            db=db,
            document_ids=doc_id_list
        )

        documents = query.all()

        if not documents:
            raise HTTPException(status_code=404, detail="No documents found")

        records = ExportService.documents_to_records(documents)

        # Export in requested format
        if format == "csv":
            data = ExportService.export_to_csv(records, include_metadata=include_metadata)
            media_type = "text/csv"
            extension = "csv"
        elif format == "excel":
            data = ExportService.export_to_excel(
                records,
                include_metadata=include_metadata,
                documents=documents,  # Pass documents for complex field expansion
                expand_complex_fields=expand_complex_fields
            )
            media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            extension = "xlsx"
        elif format == "json":
            json_str = ExportService.export_to_json(records, format_type="pretty")
            data = json_str.encode('utf-8')
            media_type = "application/json"
            extension = "json"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

        filename = f"documents_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{extension}"

        return Response(
            content=data,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid document IDs format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))
