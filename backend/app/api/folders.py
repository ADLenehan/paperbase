"""
API endpoints for virtual folder browsing and organization.
"""

import logging
from typing import List

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.folder_service import FolderService

logger = logging.getLogger(__name__)
router = APIRouter()


# Request Models
class ReorganizeRequest(BaseModel):
    extraction_ids: List[int]
    target_path: str


class SearchRequest(BaseModel):
    query: str


@router.get("/browse")
async def browse_folders(
    path: str = "",
    db: Session = Depends(get_db)
):
    """
    Browse virtual folder structure.

    Query params:
        path: Folder path (e.g., "Invoice/2025-10-11" or "" for root)

    Returns:
        {
            "current_path": "Invoice/2025-10-11",
            "folders": [
                {"name": "subfolder1", "count": 5, "path": "Invoice/2025-10-11/subfolder1"}
            ],
            "files": [
                {"id": 1, "filename": "doc.pdf", "template": "Invoice", ...}
            ],
            "total_items": 10
        }
    """
    folder_service = FolderService()
    result = folder_service.browse_folder(path, db)
    return result


@router.post("/reorganize")
async def reorganize_files(
    request: ReorganizeRequest,
    db: Session = Depends(get_db)
):
    """
    Move extractions to a different virtual folder (metadata only - no file copying!).

    Request:
        {
            "extraction_ids": [1, 2, 3],
            "target_path": "Archive/2025"
        }

    Returns:
        {
            "moved_count": 3,
            "target_path": "Archive/2025"
        }
    """
    folder_service = FolderService()

    moved_count = folder_service.reorganize_extractions(
        extraction_ids=request.extraction_ids,
        target_path=request.target_path,
        db=db
    )

    return {
        "moved_count": moved_count,
        "target_path": request.target_path
    }


@router.get("/stats")
async def get_folder_stats(
    path: str = "",
    db: Session = Depends(get_db)
):
    """
    Get statistics for a folder.

    Query params:
        path: Folder path (default: root)

    Returns:
        {
            "path": "Invoice/2025-10-11",
            "total_extractions": 25,
            "unique_files": 20,
            "by_status": {"completed": 20, "processing": 5},
            "by_template": {"Invoice": 25}
        }
    """
    folder_service = FolderService()
    stats = folder_service.get_folder_stats(path, db)
    return stats


@router.get("/search")
async def search_in_folder(
    path: str = "",
    q: str = "",
    db: Session = Depends(get_db)
):
    """
    Search for files within a folder.

    Query params:
        path: Folder path to search in
        q: Search query (matches filename)

    Returns:
        {
            "results": [
                {"id": 1, "filename": "invoice.pdf", "template": "Invoice", ...}
            ],
            "count": 5
        }
    """
    folder_service = FolderService()

    results = folder_service.search_in_folder(
        path=path,
        query=q,
        db=db
    )

    return {
        "results": results,
        "count": len(results),
        "query": q,
        "path": path
    }


@router.get("/breadcrumbs")
async def get_breadcrumbs(path: str = ""):
    """
    Get breadcrumb navigation for a path.

    Query params:
        path: Current folder path

    Returns:
        {
            "breadcrumbs": [
                {"name": "Home", "path": ""},
                {"name": "Invoice", "path": "Invoice"},
                {"name": "2025-10-11", "path": "Invoice/2025-10-11"}
            ]
        }
    """
    folder_service = FolderService()
    breadcrumbs = folder_service.get_breadcrumbs(path)

    return {
        "breadcrumbs": breadcrumbs,
        "current_path": path
    }


@router.get("/tree")
async def get_folder_tree(
    max_depth: int = 3,
    db: Session = Depends(get_db)
):
    """
    Get complete folder tree structure.

    Query params:
        max_depth: Maximum depth to traverse (default: 3)

    Returns:
        {
            "tree": [
                {
                    "name": "Invoice",
                    "path": "Invoice",
                    "children": [
                        {"name": "2025-10-11", "path": "Invoice/2025-10-11", "children": []}
                    ]
                }
            ]
        }
    """
    folder_service = FolderService()
    tree = folder_service.get_folder_tree(db, max_depth=max_depth)

    return {
        "tree": tree,
        "max_depth": max_depth
    }


@router.get("/templates")
async def get_template_folders(db: Session = Depends(get_db)):
    """
    Get all template-based top-level folders.

    Returns:
        {
            "folders": [
                {"name": "Invoice", "path": "Invoice", "count": 50},
                {"name": "Contract", "path": "Contract", "count": 30}
            ]
        }
    """
    folder_service = FolderService()

    # Browse root to get template folders
    root_data = folder_service.browse_folder("", db)

    return {
        "folders": root_data["folders"]
    }
