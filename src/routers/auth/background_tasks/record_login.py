import logging

from src.db.database import SessionLocal
from src.db.models import Logins

logger = logging.getLogger(__name__)


def record_login(account_id: int, ip_address: str) -> None:
    """
    Persist a login event for an account.

    Runs as a FastAPI background task (after the response is sent), so it must
    NOT reuse the request's DB session — that session is already closed by the
    time this runs. It opens and closes its own short-lived session instead.

    Failures are logged and swallowed: recording a login is best-effort and
    must never surface as an error to a user who has already authenticated.
    """
    db = None
    try:
        db = SessionLocal()
        db.add(Logins(account_id=account_id, ip_address=ip_address))
        db.commit()
    except Exception:
        if db is not None:
            db.rollback()
        logger.exception("Failed to record login for account_id=%s", account_id)
    finally:
        if db is not None:
            db.close()
