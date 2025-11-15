"""
Virtual folder organization service.
Provides folder browsing and reorganization without physical file duplication.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.extraction import Extraction
from app.models.physical_file import PhysicalFile
from app.models.template import SchemaTemplate

logger = logging.getLogger(__name__)


class FolderService:
    """
    Manages virtual folder structure based on extraction metadata.
    No physical file duplication - everything is metadata-driven.
    """

    def browse_folder(self, path: str, db: Session) -> Dict[str, Any]:
        """
        Browse virtual folder structure at the given path.

        Args:
            path: Folder path (e.g., "Invoice/2025-10-11" or "" for root)
            db: Database session

        Returns:
            Dict with folders and files at current level
        """
        # Normalize path
        path = path.strip("/")

        # Query extractions at or below this path
        if path:
            query = db.query(Extraction).filter(
                Extraction.organized_path.like(f"{path}/%")
            )
        else:
            query = db.query(Extraction)

        extractions = query.all()

        # Build folder tree
        folders = {}
        files = []

        current_depth = len(path.split('/')) if path else 0

        for ext in extractions:
            parts = ext.organized_path.split('/')

            if len(parts) > current_depth + 1:
                # This is a subfolder
                folder_name = parts[current_depth]
                if folder_name not in folders:
                    folders[folder_name] = {
                        "name": folder_name,
                        "count": 0,
                        "path": f"{path}/{folder_name}" if path else folder_name
                    }
                folders[folder_name]["count"] += 1
            elif len(parts) == current_depth + 1:
                # This is a file at current level
                files.append({
                    "id": ext.id,
                    "extraction_id": ext.id,
                    "physical_file_id": ext.physical_file_id,
                    "filename": ext.physical_file.filename,
                    "template": ext.template.name if ext.template else "Unknown",
                    "status": ext.status,
                    "confidence": ext.template_confidence,
                    "path": ext.organized_path,
                    "created_at": ext.created_at.isoformat()
                })

        return {
            "current_path": path,
            "folders": list(folders.values()),
            "files": files,
            "total_items": len(folders) + len(files)
        }

    def reorganize_extractions(
        self,
        extraction_ids: List[int],
        target_path: str,
        db: Session
    ) -> int:
        """
        Move extractions to a different virtual folder (metadata only!).

        Args:
            extraction_ids: List of extraction IDs to move
            target_path: Target folder path (e.g., "Contract/Archive")
            db: Database session

        Returns:
            Number of extractions moved
        """
        target_path = target_path.strip("/")
        moved_count = 0

        for ext_id in extraction_ids:
            extraction = db.query(Extraction).get(ext_id)
            if not extraction:
                logger.warning(f"Extraction #{ext_id} not found, skipping")
                continue

            # Update organized_path with new folder but keep filename
            filename = extraction.physical_file.filename
            new_path = f"{target_path}/{filename}" if target_path else filename

            logger.info(
                f"Moving extraction #{ext_id}: "
                f"{extraction.organized_path} → {new_path}"
            )

            extraction.organized_path = new_path
            moved_count += 1

        db.commit()
        logger.info(f"Reorganized {moved_count} extractions to: {target_path}")

        return moved_count

    def get_folder_stats(self, path: str, db: Session) -> Dict[str, Any]:
        """
        Get statistics for a folder.

        Args:
            path: Folder path
            db: Database session

        Returns:
            Dict with folder statistics
        """
        path = path.strip("/")

        # Count extractions in this folder and subfolders
        if path:
            query = db.query(Extraction).filter(
                Extraction.organized_path.like(f"{path}/%")
            )
        else:
            query = db.query(Extraction)

        total_extractions = query.count()

        # Count by status
        status_counts = query.with_entities(
            Extraction.status,
            func.count(Extraction.id)
        ).group_by(Extraction.status).all()

        # Count by template
        template_counts = query.join(SchemaTemplate).with_entities(
            SchemaTemplate.name,
            func.count(Extraction.id)
        ).group_by(SchemaTemplate.name).all()

        # Count unique files
        unique_files = query.with_entities(
            func.count(func.distinct(Extraction.physical_file_id))
        ).scalar()

        return {
            "path": path,
            "total_extractions": total_extractions,
            "unique_files": unique_files,
            "by_status": {status: count for status, count in status_counts},
            "by_template": {name: count for name, count in template_counts}
        }

    def create_folder_path(
        self,
        template_name: str,
        date_str: Optional[str] = None
    ) -> str:
        """
        Generate a standardized folder path.

        Args:
            template_name: Name of the template
            date_str: Optional date string (YYYY-MM-DD)

        Returns:
            Folder path string
        """
        from datetime import datetime

        if not date_str:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        return f"{template_name}/{date_str}"

    def search_in_folder(
        self,
        path: str,
        query: str,
        db: Session
    ) -> List[Dict[str, Any]]:
        """
        Search for files within a folder.

        Args:
            path: Folder path to search in
            query: Search query (matches filename)
            db: Database session

        Returns:
            List of matching extractions
        """
        path = path.strip("/")

        # Build query
        db_query = db.query(Extraction).join(PhysicalFile)

        if path:
            db_query = db_query.filter(
                Extraction.organized_path.like(f"{path}/%")
            )

        if query:
            db_query = db_query.filter(
                PhysicalFile.filename.ilike(f"%{query}%")
            )

        extractions = db_query.all()

        return [
            {
                "id": ext.id,
                "extraction_id": ext.id,
                "filename": ext.physical_file.filename,
                "template": ext.template.name if ext.template else "Unknown",
                "path": ext.organized_path,
                "status": ext.status,
                "confidence": ext.template_confidence
            }
            for ext in extractions
        ]

    def get_breadcrumbs(self, path: str) -> List[Dict[str, str]]:
        """
        Generate breadcrumb navigation for a path.

        Args:
            path: Current folder path

        Returns:
            List of breadcrumb items
        """
        path = path.strip("/")
        if not path:
            return [{"name": "Home", "path": ""}]

        breadcrumbs = [{"name": "Home", "path": ""}]
        parts = path.split('/')
        current = ""

        for part in parts:
            current = f"{current}/{part}" if current else part
            breadcrumbs.append({
                "name": part,
                "path": current
            })

        return breadcrumbs

    def get_folder_tree(self, db: Session, max_depth: int = 3) -> Dict[str, Any]:
        """
        Get complete folder tree structure.

        Args:
            db: Database session
            max_depth: Maximum depth to traverse

        Returns:
            Nested folder tree structure
        """
        # Get all unique organized paths
        paths = db.query(Extraction.organized_path).distinct().all()
        paths = [p[0] for p in paths if p[0]]

        # Build tree structure
        tree = {}

        for path in paths:
            parts = path.split('/')
            current = tree

            for i, part in enumerate(parts[:-1]):  # Exclude filename
                if i >= max_depth:
                    break

                if part not in current:
                    current[part] = {}
                current = current[part]

        return self._tree_to_list(tree)

    def _tree_to_list(self, tree: Dict[str, Any], parent_path: str = "") -> List[Dict[str, Any]]:
        """Convert tree dict to list format for frontend."""
        result = []

        for name, children in tree.items():
            path = f"{parent_path}/{name}" if parent_path else name
            item = {
                "name": name,
                "path": path,
                "children": self._tree_to_list(children, path) if children else []
            }
            result.append(item)

        return sorted(result, key=lambda x: x["name"])
