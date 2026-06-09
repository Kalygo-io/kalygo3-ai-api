"""Model A email dispatch — the single, idempotent per-recipient send path.

This module is the *one* place that renders an immutable template against a
per-send variable set + contact personalization + backend system tokens,
delivers it via SES, and writes the ``email_events`` ledger. Both the new
``POST /api/emails/send`` primitive and the legacy campaign fan-out endpoint
call :func:`dispatch_one`, so there is exactly one send code path and templates
are never mutated or cloned to carry content.

Ledger write order (at-least-once + idempotent), per recipient:
  1. ``attempting`` — written and committed *before* the SES call, so a crashed
     loop can see in-flight work on resume.
  2. ``send``       — written *after* SES acknowledges. A partial unique index on
     ``(campaign_id, contact_id) WHERE event_type='send'`` makes this the
     idempotency anchor: a duplicate insert (e.g. a re-run or a race) is caught
     and reported as ``skipped_duplicate`` instead of double-mailing.
  3. ``failed``     — written if SES raises, with the reason, for diagnostics.

Idempotency is enforced two ways: a cheap pre-check before sending, and the DB
unique index as the race-safe backstop. A rare duplicate email under a true race
is preferred to a silent drop (the index keeps the *ledger* clean regardless).
"""
import logging
import os
import re
import uuid as _uuid
from typing import Any, Dict, List, Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.db.models import Contact, EmailEvent, EmailTemplate

logger = logging.getLogger(__name__)

_TRACKING_BASE_URL = os.getenv("TRACKING_BASE_URL", "http://127.0.0.1:4000")

# Variable scopes (see TemplateVariable.scope). Drive precise validation messages.
SCOPE_CAMPAIGN = "campaign"
SCOPE_CONTACT = "contact"
SCOPE_SYSTEM = "system"


# ── Typed errors (endpoints translate these to HTTP responses) ────────────────

class MissingVariablesError(Exception):
    """Raised when one or more ``required`` template variables resolve to empty.

    ``missing`` is a list of ``{"token": str, "scope": str}`` so the caller can
    say exactly which campaign value vs. which contact personalization field is
    absent.
    """

    def __init__(self, missing: List[Dict[str, str]]):
        self.missing = missing
        tokens = ", ".join(m["token"] for m in missing)
        super().__init__(f"Unresolved required template variables: {tokens}")


class SesSendError(Exception):
    """Raised when the SES hand-off itself fails (a ``failed`` event is logged)."""


class CredentialError(Exception):
    """Raised for a missing / undecryptable / incomplete SES credential."""

    def __init__(self, detail: str, status_code: int = 422):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


# ── Rendering / delivery helpers (canonical copies) ───────────────────────────

def render_template(template_str: str, variables: Dict[str, str]) -> str:
    """Replace ``{{var}}`` / ``{{ var }}`` tokens with values from ``variables``.

    Unknown tokens are left verbatim so a missing value is visible rather than
    silently blanked. Never mutates the stored template — operates on the string.
    """
    def replacer(match: "re.Match") -> str:
        key = match.group(1).strip()
        return variables.get(key, match.group(0))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replacer, template_str)


def inject_tracking_pixel(html: str, tracking_id: str) -> str:
    """Inject a 1x1 invisible open-tracking pixel just before ``</body>``."""
    pixel = (
        f'<img src="{_TRACKING_BASE_URL}/t/o/{tracking_id}" '
        f'width="1" height="1" style="display:none;border:0;" alt="" />'
    )
    if "</body>" in html.lower():
        return re.sub(r"</body>", f"{pixel}\n</body>", html, count=1, flags=re.IGNORECASE)
    return html + pixel


def strip_html_tags(html: str) -> str:
    """Strip HTML tags and collapse whitespace for a plain-text fallback."""
    text = re.sub(r"<(br\s*/?|/?(p|div|tr|li|h[1-6])[^>]*)>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def send_ses_html_email(ses_cfg: Dict[str, Any], to_email: str, subject: str, html_body: str) -> str:
    """Send HTML email via boto3/SES. Returns the SES MessageId."""
    import boto3

    plain_fallback = strip_html_tags(html_body)
    client = boto3.client(
        "ses",
        region_name=ses_cfg["aws_region"],
        aws_access_key_id=ses_cfg["aws_access_key_id"],
        aws_secret_access_key=ses_cfg["aws_secret_access_key"],
    )
    response = client.send_email(
        Source=ses_cfg["from_email"],
        Destination={"ToAddresses": [to_email]},
        Message={
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html_body, "Charset": "UTF-8"},
                "Text": {"Data": plain_fallback, "Charset": "UTF-8"},
            },
        },
    )
    return response.get("MessageId", "unknown")


# ── Variable resolution + validation ──────────────────────────────────────────

def build_system_tokens(tracking_id: str) -> Dict[str, str]:
    """Backend-injected tokens — always win over request/contact/default values."""
    rating_base = f"{_TRACKING_BASE_URL}/t/r/{tracking_id}"
    return {
        "RATING_BASE_URL": rating_base,
        "rating_base_url": rating_base,
        "tracking_id": tracking_id,
        "TRACKING_ID": tracking_id,
    }


def build_contact_tokens(contact: Contact) -> Dict[str, str]:
    """Contact-scoped personalization tokens, lower- and upper-case variants."""
    return {
        "first_name": contact.first_name or "",
        "last_name": contact.last_name or "",
        "name": contact.name or "",
        "email": contact.email or "",
        "FIRST_NAME": contact.first_name or "",
        "LAST_NAME": contact.last_name or "",
        "NAME": contact.name or "",
        "EMAIL": contact.email or "",
    }


def resolve_variables(
    template: EmailTemplate,
    request_vars: Optional[Dict[str, Any]],
    contact: Optional[Contact],
    tracking_id: str,
) -> Dict[str, str]:
    """Merge token sources by precedence (low → high):

        template variable ``default``  <  request ``variables``
                                       <  contact fields  <  system tokens
    """
    resolved: Dict[str, str] = {}
    for v in (template.variables or []):
        name = v.get("name")
        if name:
            resolved[name] = v.get("default") or ""
    for k, val in (request_vars or {}).items():
        resolved[k] = "" if val is None else str(val)
    if contact is not None:
        resolved.update(build_contact_tokens(contact))
    resolved.update(build_system_tokens(tracking_id))
    return resolved


def find_missing_required(
    template: EmailTemplate, resolved: Dict[str, str]
) -> List[Dict[str, str]]:
    """Return ``{token, scope}`` for every ``required`` variable resolving empty."""
    missing: List[Dict[str, str]] = []
    for v in (template.variables or []):
        if not v.get("required"):
            continue
        name = v.get("name")
        if not name:
            continue
        value = resolved.get(name)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append({"token": name, "scope": v.get("scope") or SCOPE_CAMPAIGN})
    return missing


# ── Idempotency + dispatch ────────────────────────────────────────────────────

def existing_send_event(
    db: Session, account_id: int, campaign_id: int, contact_id: Optional[int]
) -> Optional[EmailEvent]:
    """The confirmed ``send`` event for this (campaign, contact), if any.

    Ad-hoc sends (no contact_id) are never deduped — there is no stable identity
    to key on — so this returns ``None`` for them.
    """
    if contact_id is None:
        return None
    return (
        db.query(EmailEvent)
        .filter(
            EmailEvent.account_id == account_id,
            EmailEvent.campaign_id == campaign_id,
            EmailEvent.contact_id == contact_id,
            EmailEvent.event_type == "send",
        )
        .first()
    )


def _tracking_of(event: Optional[EmailEvent]) -> Optional[str]:
    if event and event.event_metadata:
        return event.event_metadata.get("tracking_id")
    return None


def dispatch_one(
    db: Session,
    *,
    account_id: int,
    campaign_id: int,
    template: EmailTemplate,
    contact: Optional[Contact],
    to_email: str,
    request_vars: Optional[Dict[str, Any]],
    credential_cfg: Dict[str, Any],
    credential_id: int,
    dry_run: bool = False,
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Render → validate → (dedup) → send → log, for a single recipient.

    Returns ``{status, tracking_id, event_id, contact_id, campaign_id}`` where
    ``status`` is ``"sent" | "skipped_duplicate" | "validated"``.

    Raises :class:`MissingVariablesError` (422) or :class:`SesSendError` (502).
    """
    tracking_id = str(_uuid.uuid4())
    contact_id = contact.id if contact is not None else None

    resolved = resolve_variables(template, request_vars, contact, tracking_id)
    missing = find_missing_required(template, resolved)
    if missing:
        raise MissingVariablesError(missing)

    # dry_run validates everything above without touching SES or the ledger.
    if dry_run:
        return {
            "status": "validated",
            "tracking_id": tracking_id,
            "event_id": None,
            "contact_id": contact_id,
            "campaign_id": campaign_id,
        }

    # Idempotency pre-check (cheap path; the unique index is the race backstop).
    existing = existing_send_event(db, account_id, campaign_id, contact_id)
    if existing is not None:
        return {
            "status": "skipped_duplicate",
            "tracking_id": _tracking_of(existing) or tracking_id,
            "event_id": existing.id,
            "contact_id": contact_id,
            "campaign_id": campaign_id,
        }

    subject = render_template(template.subject_template, resolved)
    html = render_template(template.html_template, resolved)
    html = inject_tracking_pixel(html, tracking_id)

    from_email = credential_cfg.get("from_email", "")
    sender_domain = from_email.split("@")[1] if "@" in from_email else None
    recipient_lower = to_email.strip().lower()

    base_meta = {
        "tracking_id": tracking_id,
        "email_template_id": template.id,
    }
    if batch_id:
        base_meta["batch_id"] = batch_id

    # (1) attempting — committed BEFORE the SES call so resume sees in-flight work.
    attempting = EmailEvent(
        account_id=account_id,
        campaign_id=campaign_id,
        contact_id=contact_id,
        primary_recipient=recipient_lower,
        event_type="attempting",
        provider="ses",
        credential_id=credential_id,
        sender_domain=sender_domain,
        event_metadata={**base_meta},
    )
    db.add(attempting)
    db.commit()
    db.refresh(attempting)

    # (2) SES hand-off.
    try:
        message_id = send_ses_html_email(credential_cfg, to_email, subject, html)
    except Exception as exc:  # noqa: BLE001 — record the reason then surface it
        db.rollback()
        try:
            db.add(EmailEvent(
                account_id=account_id,
                campaign_id=campaign_id,
                contact_id=contact_id,
                primary_recipient=recipient_lower,
                event_type="failed",
                provider="ses",
                credential_id=credential_id,
                sender_domain=sender_domain,
                event_metadata={**base_meta, "reason": str(exc),
                                "attempting_event_id": attempting.id},
            ))
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
            logger.exception("Failed to record 'failed' event for %s", recipient_lower)
        raise SesSendError(str(exc)) from exc

    # (3) send — confirmed. The partial unique index turns a lost race into a
    #     clean skipped_duplicate rather than a second mailing in the ledger.
    send_ev = EmailEvent(
        account_id=account_id,
        campaign_id=campaign_id,
        contact_id=contact_id,
        primary_recipient=recipient_lower,
        event_type="send",
        provider="ses",
        message_id=message_id,
        credential_id=credential_id,
        sender_domain=sender_domain,
        event_metadata={**base_meta, "attempting_event_id": attempting.id},
    )
    db.add(send_ev)
    try:
        db.commit()
    except IntegrityError:
        # Another writer recorded the confirmed send first (unique index).
        db.rollback()
        existing = existing_send_event(db, account_id, campaign_id, contact_id)
        return {
            "status": "skipped_duplicate",
            "tracking_id": _tracking_of(existing) or tracking_id,
            "event_id": existing.id if existing else None,
            "contact_id": contact_id,
            "campaign_id": campaign_id,
        }
    db.refresh(send_ev)

    return {
        "status": "sent",
        "tracking_id": tracking_id,
        "event_id": send_ev.id,
        "contact_id": contact_id,
        "campaign_id": campaign_id,
    }


# ── Credential loading (shared by both send endpoints) ────────────────────────

_REQUIRED_SES_FIELDS = ["aws_access_key_id", "aws_secret_access_key", "aws_region", "from_email"]


def load_ses_credential(db: Session, account_id: int, credential_id: int) -> Dict[str, Any]:
    """Load, decrypt, and validate an SES credential. Raises :class:`CredentialError`."""
    from src.db.models import Credential
    from src.routers.credentials.encryption import decrypt_credential_data

    credential = (
        db.query(Credential)
        .filter(Credential.id == credential_id, Credential.account_id == account_id)
        .first()
    )
    if not credential:
        raise CredentialError("Credential not found", status_code=404)

    try:
        cred_data = decrypt_credential_data(credential.encrypted_data)
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to decrypt credential %d: %s", credential_id, exc)
        raise CredentialError("Failed to decrypt credential", status_code=500) from exc

    missing = [k for k in _REQUIRED_SES_FIELDS if not cred_data.get(k)]
    if missing:
        raise CredentialError(
            f"Credential is missing required SES fields: {', '.join(missing)}"
        )
    return cred_data
