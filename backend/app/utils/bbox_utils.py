"""
Bounding box utilities for converting between formats

Reducto returns bboxes as dicts: {left: x, top: y, width: w, height: h, page: p}
Frontend expects arrays: [x, y, width, height]
"""

from typing import Any, List, Optional


def normalize_bbox(bbox: Any) -> Optional[List[float]]:
    """
    Convert bbox from any format to frontend-compatible array format.

    Args:
        bbox: Bounding box in various formats:
            - Dict: {left: x, top: y, width: w, height: h, ...}
            - Array: [x, y, width, height]
            - None

    Returns:
        Array [x, y, width, height] or None if invalid

    Examples:
        >>> normalize_bbox({left: 10, top: 20, width: 100, height: 50})
        [10, 20, 100, 50]

        >>> normalize_bbox([10, 20, 100, 50])
        [10, 20, 100, 50]

        >>> normalize_bbox(None)
        None
    """
    if bbox is None:
        return None

    # Already in array format
    if isinstance(bbox, (list, tuple)):
        if len(bbox) >= 4:
            # Ensure all values are floats
            return [float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])]
        return None

    # Dictionary format (from Reducto)
    if isinstance(bbox, dict):
        # Try standard keys: left, top, width, height
        if all(k in bbox for k in ['left', 'top', 'width', 'height']):
            return [
                float(bbox['left']),
                float(bbox['top']),
                float(bbox['width']),
                float(bbox['height'])
            ]

        # Try alternative keys: x, y, w, h
        if all(k in bbox for k in ['x', 'y', 'w', 'h']):
            return [
                float(bbox['x']),
                float(bbox['y']),
                float(bbox['w']),
                float(bbox['h'])
            ]

        # Try alternative keys: x, y, width, height
        if all(k in bbox for k in ['x', 'y', 'width', 'height']):
            return [
                float(bbox['x']),
                float(bbox['y']),
                float(bbox['width']),
                float(bbox['height'])
            ]

    return None


def format_bbox_for_frontend(bbox: Any, page: Optional[int] = None) -> Optional[dict]:
    """
    Format bbox with page number for frontend consumption.

    Args:
        bbox: Raw bbox in any format
        page: Page number (1-indexed)

    Returns:
        Dict with normalized bbox and page, or None if invalid
        {
            "bbox": [x, y, width, height],
            "page": 1
        }
    """
    normalized = normalize_bbox(bbox)
    if normalized is None:
        return None

    result = {"bbox": normalized}

    # Add page if provided or if it's in the bbox dict
    if page is not None:
        result["page"] = int(page)
    elif isinstance(bbox, dict) and "page" in bbox:
        result["page"] = int(bbox["page"])

    return result
