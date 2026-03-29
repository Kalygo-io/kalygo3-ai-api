"""
Centralised database / request error handling.

Usage in routers:
    from src.utils.errors import handle_db_error

    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CONTACT]")
"""
import logging
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger(__name__)


def handle_db_error(e: Exception, log_prefix: str) -> HTTPException:
    """
    Map a caught exception to a safe HTTPException.

    - Logs the full error server-side.
    - Never leaks internal error strings (SQL, stack traces, etc.) to the client.
    - Returns meaningful HTTP status codes for known constraint violations.
    """
    logger.error("%s %s: %s", log_prefix, type(e).__name__, e)

    if isinstance(e, IntegrityError):
        orig = getattr(e, "orig", None)
        msg = str(orig).lower() if orig else str(e).lower()

        if "unique" in msg or "duplicate" in msg:
            return HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A record with that value already exists.",
            )
        if "foreign key" in msg or "violates foreign" in msg:
            return HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The request references a resource that does not exist.",
            )
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The request conflicts with existing data.",
        )

    if isinstance(e, SQLAlchemyError):
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A database error occurred. Please try again.",
        )

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected error occurred. Please try again.",
    )
