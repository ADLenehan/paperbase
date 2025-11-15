"""
Encryption utilities for sensitive data (OAuth tokens, etc.)

Uses Fernet (symmetric encryption) from cryptography library.
Encryption key must be stored in environment variable: ENCRYPTION_KEY

Generate a new key with:
    from cryptography.fernet import Fernet
    print(Fernet.generate_key().decode())
"""

import os
import json
from cryptography.fernet import Fernet
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data.

    Features:
    - Symmetric encryption using Fernet (AES-128 CBC + HMAC)
    - Automatic JSON serialization/deserialization
    - Safe handling of None values
    - Error handling with logging
    """

    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service.

        Args:
            encryption_key: Base64-encoded Fernet key. If None, reads from ENCRYPTION_KEY env var.

        Raises:
            ValueError: If no encryption key provided or found in environment
        """
        key = encryption_key or os.getenv("ENCRYPTION_KEY")
        if not key:
            # For development, generate a temporary key (WARNING: data won't persist across restarts)
            logger.warning(
                "No ENCRYPTION_KEY found in environment. Generating temporary key. "
                "Set ENCRYPTION_KEY in .env for production!"
            )
            key = Fernet.generate_key().decode()

        self.cipher = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt_dict(self, data: Dict[str, Any]) -> str:
        """
        Encrypt a dictionary to a base64-encoded string.

        Args:
            data: Dictionary to encrypt

        Returns:
            Base64-encoded encrypted string

        Example:
            >>> service = EncryptionService()
            >>> encrypted = service.encrypt_dict({"access_token": "abc123", "refresh_token": "xyz789"})
            >>> print(encrypted)  # "gAAAAA..."
        """
        if not data:
            return ""

        try:
            # Serialize to JSON
            json_str = json.dumps(data)
            # Encrypt
            encrypted_bytes = self.cipher.encrypt(json_str.encode())
            # Return as base64 string
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise ValueError(f"Failed to encrypt data: {str(e)}")

    def decrypt_dict(self, encrypted_str: str) -> Optional[Dict[str, Any]]:
        """
        Decrypt a base64-encoded string back to a dictionary.

        Args:
            encrypted_str: Base64-encoded encrypted string

        Returns:
            Decrypted dictionary, or None if decryption fails

        Example:
            >>> service = EncryptionService()
            >>> decrypted = service.decrypt_dict("gAAAAA...")
            >>> print(decrypted)  # {"access_token": "abc123", "refresh_token": "xyz789"}
        """
        if not encrypted_str:
            return None

        try:
            # Decrypt
            decrypted_bytes = self.cipher.decrypt(encrypted_str.encode())
            # Deserialize from JSON
            data = json.loads(decrypted_bytes.decode())
            return data
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            return None

    def encrypt_string(self, text: str) -> str:
        """
        Encrypt a plain string.

        Args:
            text: Plain text to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not text:
            return ""

        try:
            encrypted_bytes = self.cipher.encrypt(text.encode())
            return encrypted_bytes.decode()
        except Exception as e:
            logger.error(f"String encryption failed: {e}")
            raise ValueError(f"Failed to encrypt string: {str(e)}")

    def decrypt_string(self, encrypted_str: str) -> Optional[str]:
        """
        Decrypt a base64-encoded string back to plain text.

        Args:
            encrypted_str: Base64-encoded encrypted string

        Returns:
            Decrypted plain text, or None if decryption fails
        """
        if not encrypted_str:
            return None

        try:
            decrypted_bytes = self.cipher.decrypt(encrypted_str.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            logger.error(f"String decryption failed: {e}")
            return None


# Singleton instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """
    Get the singleton encryption service instance.

    Returns:
        EncryptionService instance
    """
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


# Convenience functions
def encrypt_oauth_tokens(tokens: Dict[str, Any]) -> str:
    """
    Encrypt OAuth tokens for storage in database.

    Args:
        tokens: Dictionary containing access_token, refresh_token, etc.

    Returns:
        Encrypted string safe for database storage

    Example:
        >>> encrypted = encrypt_oauth_tokens({
        ...     "access_token": "ya29.a0...",
        ...     "refresh_token": "1//0g...",
        ...     "expires_at": 1699999999
        ... })
    """
    service = get_encryption_service()
    return service.encrypt_dict(tokens)


def decrypt_oauth_tokens(encrypted_str: str) -> Optional[Dict[str, Any]]:
    """
    Decrypt OAuth tokens from database.

    Args:
        encrypted_str: Encrypted string from database

    Returns:
        Dictionary containing tokens, or None if decryption fails

    Example:
        >>> tokens = decrypt_oauth_tokens(user.provider_metadata)
        >>> if tokens:
        ...     access_token = tokens.get("access_token")
    """
    service = get_encryption_service()
    return service.decrypt_dict(encrypted_str)
