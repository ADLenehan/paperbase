"""
Error handling middleware and exception handlers for FastAPI.
"""
import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .exceptions import (
    PaperbaseException,
)

logger = logging.getLogger(__name__)


async def paperbase_exception_handler(request: Request, exc: PaperbaseException) -> JSONResponse:
    """
    Handle all custom Paperbase exceptions.

    Args:
        request: The FastAPI request object
        exc: The exception that was raised

    Returns:
        JSONResponse with error details
    """
    logger.error(
        f"Paperbase exception: {exc.message}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "status_code": exc.status_code,
            "exception_type": exc.__class__.__name__
        }
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "message": exc.message,
            "path": str(request.url.path)
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle FastAPI validation errors.

    Args:
        request: The FastAPI request object
        exc: The validation error

    Returns:
        JSONResponse with validation error details
    """
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        f"Validation error on {request.method} {request.url.path}",
        extra={"errors": errors}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "message": "Request validation failed",
            "details": errors,
            "path": str(request.url.path)
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """
    Handle standard HTTP exceptions.

    Args:
        request: The FastAPI request object
        exc: The HTTP exception

    Returns:
        JSONResponse with error details
    """
    logger.warning(
        f"HTTP {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTPException",
            "message": exc.detail,
            "path": str(request.url.path)
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Catch-all handler for unexpected exceptions.

    Args:
        request: The FastAPI request object
        exc: The unexpected exception

    Returns:
        JSONResponse with generic error message
    """
    logger.error(
        f"Unexpected error on {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
        extra={
            "exception_type": exc.__class__.__name__,
            "exception_message": str(exc)
        }
    )

    # Don't expose internal error details in production
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred. Please try again later.",
            "path": str(request.url.path)
        }
    )


def register_error_handlers(app):
    """
    Register all error handlers with the FastAPI application.

    Args:
        app: The FastAPI application instance
    """
    # Custom Paperbase exceptions
    app.add_exception_handler(PaperbaseException, paperbase_exception_handler)

    # FastAPI validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Standard HTTP exceptions
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)

    # Catch-all for unexpected errors
    app.add_exception_handler(Exception, general_exception_handler)

    logger.info("Error handlers registered successfully")
