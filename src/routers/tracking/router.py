"""
Email open-tracking endpoint.

GET /t/o/{tracking_id}

Called when a recipient's mail client loads the invisible 1×1 pixel that was
injected into the HTML email at send time.  Looks up the email_events row
whose event_metadata->tracking_id matches, then inserts a new "open" event
linked to the same tool_approval_id / primary_recipient.

Returns a 1×1 transparent GIF so mail clients don't show a broken-image icon.
"""
import base64
from fastapi import APIRouter
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.db.database import SessionLocal
from src.db.models import EmailEvent

router = APIRouter()

# Smallest valid 1×1 transparent GIF (43 bytes)
_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/o/{tracking_id}")
async def track_open(tracking_id: str):
    """Record an email open event and return a 1×1 transparent GIF."""
    db: Session = SessionLocal()
    try:
        send_event = (
            db.query(EmailEvent)
            .filter(
                EmailEvent.event_type == "send_to_ses",
                EmailEvent.event_metadata["tracking_id"].as_string() == tracking_id,
            )
            .first()
        )

        if send_event:
            already_opened = (
                db.query(EmailEvent)
                .filter(
                    EmailEvent.tool_approval_id == send_event.tool_approval_id,
                    EmailEvent.event_type == "open",
                    EmailEvent.event_metadata["tracking_id"].as_string() == tracking_id,
                )
                .first()
            )
            if not already_opened:
                open_event = EmailEvent(
                    account_id=send_event.account_id,
                    tool_approval_id=send_event.tool_approval_id,
                    primary_recipient=send_event.primary_recipient,
                    event_type="open",
                    provider=send_event.provider,
                    message_id=send_event.message_id,
                    event_metadata={"tracking_id": tracking_id},
                )
                db.add(open_event)
                db.commit()
    except Exception as exc:
        print(f"[TRACKING] ⚠️  open tracking error for {tracking_id}: {exc}")
    finally:
        db.close()

    return Response(
        content=_PIXEL_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )
