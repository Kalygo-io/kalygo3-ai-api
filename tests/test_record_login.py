"""
Regression tests for login tracking.

These guard the two bugs that previously prevented logins from being recorded:
  1. The router imported the *module* `record_login` instead of the function,
     so the background task was not callable.
  2. `record_login` reused the request's DB session, which FastAPI closes
     before background tasks run, so the commit silently failed.

The fix makes `record_login` a plain callable that opens its own short-lived
session. These tests exercise that real code path against the test database,
patching the module's SessionLocal onto the non-SSL test engine.
"""
import pytest
from sqlalchemy.orm import sessionmaker

from tests.conftest import test_engine
from src.routers.auth.background_tasks import record_login as record_login_module
from src.routers.auth.background_tasks.record_login import record_login
from src.db.models import Account, Logins

# A session factory bound to the test engine, mirroring the app's SessionLocal
# but without the production SSL requirement.
_TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture()
def account_id():
    """Create a committed account and clean it (and its logins) up afterwards."""
    session = _TestSessionLocal()
    acct = Account(email="record-login-test@example.com")
    session.add(acct)
    session.commit()
    session.refresh(acct)
    acct_id = acct.id
    session.close()

    yield acct_id

    cleanup = _TestSessionLocal()
    cleanup.query(Logins).filter(Logins.account_id == acct_id).delete()
    cleanup.query(Account).filter(Account.id == acct_id).delete()
    cleanup.commit()
    cleanup.close()


def test_router_imports_callable_function():
    """The router must import the function, not the (non-callable) module."""
    import sys
    import src.routers.auth.router  # noqa: F401 — ensure it's in sys.modules
    auth_router_module = sys.modules["src.routers.auth.router"]

    assert callable(auth_router_module.record_login)
    assert auth_router_module.record_login is record_login


def test_record_login_persists_a_row(account_id, monkeypatch):
    monkeypatch.setattr(record_login_module, "SessionLocal", _TestSessionLocal)

    record_login(account_id, "203.0.113.7")

    verify = _TestSessionLocal()
    rows = verify.query(Logins).filter(Logins.account_id == account_id).all()
    verify.close()

    assert len(rows) == 1
    assert rows[0].ip_address == "203.0.113.7"
    assert rows[0].created_at is not None


def test_record_login_swallows_errors(account_id, monkeypatch):
    """A failure while recording a login must not raise (best-effort)."""

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(record_login_module, "SessionLocal", boom)

    # Should not raise despite the session factory blowing up.
    record_login(account_id, "203.0.113.7")
