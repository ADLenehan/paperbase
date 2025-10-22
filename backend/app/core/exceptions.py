"""
Custom exceptions for Paperbase application.
"""


class PaperbaseException(Exception):
    """Base exception for all Paperbase errors"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class ValidationError(PaperbaseException):
    """Raised when input validation fails"""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class NotFoundError(PaperbaseException):
    """Raised when a requested resource is not found"""
    def __init__(self, resource: str, identifier: str):
        message = f"{resource} with identifier '{identifier}' not found"
        super().__init__(message, status_code=404)


class ExternalServiceError(PaperbaseException):
    """Raised when an external service (Reducto, Claude, Elasticsearch) fails"""
    def __init__(self, service: str, message: str, original_error: Exception = None):
        self.service = service
        self.original_error = original_error
        full_message = f"{service} service error: {message}"
        if original_error:
            full_message += f" (Original: {str(original_error)})"
        super().__init__(full_message, status_code=502)


class ReductoError(ExternalServiceError):
    """Raised when Reducto API fails"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__("Reducto", message, original_error)


class ClaudeError(ExternalServiceError):
    """Raised when Claude API fails"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__("Claude", message, original_error)


class ElasticsearchError(ExternalServiceError):
    """Raised when Elasticsearch fails"""
    def __init__(self, message: str, original_error: Exception = None):
        super().__init__("Elasticsearch", message, original_error)


class ProcessingError(PaperbaseException):
    """Raised when document processing fails"""
    def __init__(self, document_id: str, message: str):
        self.document_id = document_id
        full_message = f"Failed to process document {document_id}: {message}"
        super().__init__(full_message, status_code=500)


class SchemaError(PaperbaseException):
    """Raised when schema validation or operations fail"""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class FileUploadError(PaperbaseException):
    """Raised when file upload fails"""
    def __init__(self, message: str):
        super().__init__(message, status_code=400)


class ConfigurationError(PaperbaseException):
    """Raised when there's a configuration issue"""
    def __init__(self, message: str):
        super().__init__(message, status_code=500)
