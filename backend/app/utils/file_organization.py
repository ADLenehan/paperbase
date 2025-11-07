"""
File organization utilities for template-based folder structure.

Organizes uploaded documents into folders by template:
uploads/
  ├── invoice/
  ├── w2/
  ├── passport/
  └── unmatched/
"""

import os
import shutil
from pathlib import Path
from typing import Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def get_template_folder(template_name: Optional[str] = None) -> str:
    """
    Get the folder path for a template.

    Args:
        template_name: Name of the template (e.g., "Invoice", "W2")
                      If None, returns "unmatched" folder

    Returns:
        Absolute path to the template folder
    """
    base_dir = Path(settings.UPLOAD_DIR)

    if template_name:
        # Sanitize template name for folder (lowercase, replace spaces with underscores)
        folder_name = template_name.lower().replace(" ", "_").replace("/", "_")
    else:
        folder_name = "unmatched"

    template_dir = base_dir / folder_name
    template_dir.mkdir(parents=True, exist_ok=True)

    return str(template_dir)


def organize_document_file(
    current_path: str,
    filename: str,
    template_name: Optional[str] = None
) -> str:
    """
    Move document to appropriate template folder.

    Args:
        current_path: Current path of the document
        filename: Original filename
        template_name: Template name for folder organization

    Returns:
        New file path after organization
    """
    template_folder = get_template_folder(template_name)
    new_path = os.path.join(template_folder, filename)

    # If file already exists at destination, append timestamp
    if os.path.exists(new_path):
        from datetime import datetime
        timestamp = datetime.utcnow().timestamp()
        name, ext = os.path.splitext(filename)
        new_path = os.path.join(template_folder, f"{name}_{timestamp}{ext}")

    # Move file
    try:
        shutil.move(current_path, new_path)
        logger.info(f"Organized file: {filename} → {template_name or 'unmatched'}")
        return new_path
    except Exception as e:
        logger.error(f"Failed to organize file {filename}: {e}")
        return current_path  # Return original path if move fails


def organize_document_file_copy(
    current_path: str,
    filename: str,
    template_name: Optional[str] = None
) -> str:
    """
    Copy (not move) document to appropriate template folder.

    This is used when multiple Documents share the same PhysicalFile via deduplication.
    We copy instead of move to preserve the original PhysicalFile for other Documents.

    Args:
        current_path: Current path of the document
        filename: Original filename
        template_name: Template name for folder organization

    Returns:
        New file path after copying
    """
    template_folder = get_template_folder(template_name)
    new_path = os.path.join(template_folder, filename)

    # If file already exists at destination, append timestamp
    if os.path.exists(new_path):
        from datetime import datetime
        timestamp = datetime.utcnow().timestamp()
        name, ext = os.path.splitext(filename)
        new_path = os.path.join(template_folder, f"{name}_{timestamp}{ext}")

    # Copy file (preserve original)
    try:
        shutil.copy2(current_path, new_path)
        logger.info(f"Copied file for organization: {filename} → {template_name or 'unmatched'}")
        return new_path
    except Exception as e:
        logger.error(f"Failed to copy file {filename}: {e}")
        return current_path  # Return original path if copy fails


def get_template_document_count(template_name: str) -> int:
    """
    Count documents in a template folder.

    Args:
        template_name: Template name

    Returns:
        Number of documents in the template folder
    """
    template_folder = get_template_folder(template_name)
    if not os.path.exists(template_folder):
        return 0

    return len([f for f in os.listdir(template_folder) if os.path.isfile(os.path.join(template_folder, f))])


def list_template_folders() -> list[dict]:
    """
    List all template folders with document counts.

    Returns:
        List of dicts with template info: [{"name": "invoice", "count": 10}, ...]
    """
    base_dir = Path(settings.UPLOAD_DIR)
    if not base_dir.exists():
        return []

    folders = []
    for item in base_dir.iterdir():
        if item.is_dir():
            count = len([f for f in item.iterdir() if f.is_file()])
            folders.append({
                "name": item.name,
                "count": count,
                "path": str(item)
            })

    return sorted(folders, key=lambda x: x["count"], reverse=True)
