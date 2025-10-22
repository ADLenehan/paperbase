import hashlib
from typing import BinaryIO


def calculate_file_hash(file_path: str) -> str:
    """
    Calculate SHA256 hash of a file for deduplication.

    Args:
        file_path: Path to the file

    Returns:
        Hexadecimal SHA256 hash string
    """
    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read in chunks to handle large files
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)

    return sha256_hash.hexdigest()


def calculate_content_hash(content: bytes) -> str:
    """
    Calculate SHA256 hash of file content (already in memory).

    Args:
        content: File content as bytes

    Returns:
        Hexadecimal SHA256 hash string
    """
    return hashlib.sha256(content).hexdigest()
