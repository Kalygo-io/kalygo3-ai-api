"""
Email tracking endpoints (public, no auth).

GET /t/o/{tracking_id}          — open-tracking pixel
GET /t/r/{tracking_id}/{rating} — star-rating click
"""
import logging
import base64
from fastapi import APIRouter, Depends, Path
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session

from src.deps import get_db
from src.db.models import EmailCampaignRating, EmailEvent

logger = logging.getLogger(__name__)

router = APIRouter()

_PIXEL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


@router.get("/o/{tracking_id}")
async def track_open(tracking_id: str, db: Session = Depends(get_db)):
    """Record an email open event and return a 1x1 transparent GIF."""
    try:
        send_event = (
            db.query(EmailEvent)
            .filter(
                # "send_to_ses" is the hand-off event (Model A dispatch and the
                # legacy tool-approval path both write it) and carries the
                # tracking_id in event_metadata. The bare "send" type is reserved
                # for SES SNS notifications, which key off the SES message_id, not
                # our tracking_id — so they are deliberately not matched here.
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
                    campaign_id=send_event.campaign_id,
                    contact_id=send_event.contact_id,
                    primary_recipient=send_event.primary_recipient,
                    event_type="open",
                    provider=send_event.provider,
                    message_id=send_event.message_id,
                    event_metadata={"tracking_id": tracking_id},
                )
                db.add(open_event)
                db.commit()
    except Exception:
        logger.exception("[TRACKING] Open tracking error for %s", tracking_id)
        db.rollback()

    return Response(
        content=_PIXEL_GIF,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
        },
    )


_THANK_YOU_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thank you!</title>
<style>
  body { margin:0; font-family:'Trebuchet MS',Arial,sans-serif;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; background:#f7f7f7; color:#0a080b; }
  .card { text-align:center; padding:60px 40px; background:#fff;
          border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,.08);
          max-width:420px; }
  .stars { font-size:40px; color:#028383; letter-spacing:4px; margin:20px 0; }
  .dim   { color:#ccc; }
  h1 { font-size:28px; font-weight:normal; margin:0 0 8px; }
  p  { font-size:16px; line-height:24px; color:#555; margin:0; }
</style>
</head>
<body>
<div class="card">
  <div class="stars">STARS_PLACEHOLDER</div>
  <h1>Thank you for your feedback!</h1>
  <p>You rated your experience RATING_PLACEHOLDER out of 5.<br>
     You can close this tab now.</p>
</div>
</body>
</html>
"""


_UNKNOWN_LINK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Link not recognized</title>
<style>
  body { margin:0; font-family:'Trebuchet MS',Arial,sans-serif;
         display:flex; align-items:center; justify-content:center;
         min-height:100vh; background:#f7f7f7; color:#0a080b; }
  .card { text-align:center; padding:60px 40px; background:#fff;
          border-radius:12px; box-shadow:0 2px 12px rgba(0,0,0,.08);
          max-width:420px; }
  h1 { font-size:28px; font-weight:normal; margin:0 0 8px; }
  p  { font-size:16px; line-height:24px; color:#555; margin:0; }
</style>
</head>
<body>
<div class="card">
  <h1>This rating link isn't valid</h1>
  <p>The link may have expired or been mistyped. You can close this tab.</p>
</div>
</body>
</html>
"""


def _render_thank_you(rating: int) -> str:
    filled = "\u2605" * rating
    empty = '<span class="dim">\u2605</span>' * (5 - rating)
    return (
        _THANK_YOU_HTML
        .replace("STARS_PLACEHOLDER", filled + empty)
        .replace("RATING_PLACEHOLDER", str(rating))
    )


@router.get("/r/{tracking_id}/{rating}")
async def track_rating(
    tracking_id: str,
    rating: int = Path(..., ge=1, le=5),
    db: Session = Depends(get_db),
):
    """Record a star-rating click from an email and show a thank-you page."""
    logger.info("[RATING] Received rating=%d for tracking_id=%s", rating, tracking_id)
    resolved = False  # did this tracking_id map to a real send (or prior rating)?
    try:
        already_rated = (
            db.query(EmailCampaignRating)
            .filter(EmailCampaignRating.tracking_id == tracking_id)
            .first()
        )

        if already_rated:
            resolved = True
            logger.info(
                "[RATING] Duplicate — tracking_id=%s already has rating=%d (id=%d), skipping",
                tracking_id, already_rated.rating, already_rated.id,
            )
        else:
            send_event = (
                db.query(EmailEvent)
                .filter(
                    # The hand-off event carrying our tracking_id (see track_open).
                    EmailEvent.event_type == "send_to_ses",
                    EmailEvent.event_metadata["tracking_id"].as_string() == tracking_id,
                )
                .first()
            )

            if not send_event:
                logger.warning(
                    "[RATING] No send event found for tracking_id=%s — rating will not be stored",
                    tracking_id,
                )
            else:
                resolved = True
                metadata = send_event.event_metadata or {}
                logger.info(
                    "[RATING] Matched send_event id=%d account_id=%d campaign_id=%s "
                    "email_template_id=%s contact_id=%s recipient=%s",
                    send_event.id, send_event.account_id, send_event.campaign_id,
                    metadata.get("email_template_id"), send_event.contact_id,
                    send_event.primary_recipient,
                )
                rating_row = EmailCampaignRating(
                    account_id=send_event.account_id,
                    campaign_id=send_event.campaign_id,
                    email_template_id=metadata.get("email_template_id"),
                    contact_id=send_event.contact_id,
                    primary_recipient=send_event.primary_recipient,
                    tracking_id=tracking_id,
                    rating=rating,
                )
                db.add(rating_row)
                db.commit()
                db.refresh(rating_row)
                logger.info(
                    "[RATING] Stored rating id=%d rating=%d for tracking_id=%s",
                    rating_row.id, rating_row.rating, tracking_id,
                )
    except Exception:
        logger.exception("[RATING] Failed to store rating for tracking_id=%s", tracking_id)
        db.rollback()

    if not resolved:
        # Unknown/unresolvable tracking_id → 404 rather than a silent 200. The
        # old silent 200 is exactly what masked the attribution gap: a bogus id
        # was indistinguishable from a recorded rating.
        logger.warning("[RATING] Unresolved tracking_id=%s → returning 404", tracking_id)
        return HTMLResponse(
            content=_UNKNOWN_LINK_HTML,
            status_code=404,
            headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
        )

    return HTMLResponse(
        content=_render_thank_you(rating),
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        },
    )
