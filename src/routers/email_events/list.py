"""
List email events endpoint — with filters suited for a metrics dashboard.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, status, Request, Query
from src.deps import db_dependency, auth_dependency
from src.db.models import EmailEvent
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import EmailEventResponse, EmailEventStatsResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[EmailEventResponse])
@limiter.limit("60/minute")
async def list_email_events(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    event_type: Optional[str] = Query(default=None, description="Filter by event type: send|delivery|open|bounce|complaint|other"),
    contact_id: Optional[int] = Query(default=None),
    campaign_id: Optional[int] = Query(default=None),
    tool_approval_id: Optional[int] = Query(default=None),
    primary_recipient: Optional[str] = Query(default=None, description="Filter by primary recipient email (case-insensitive)"),
    provider: Optional[str] = Query(default=None, description="Filter by provider: ses|google_oauth|google_smtp"),
    from_date: Optional[datetime] = Query(default=None, description="Start of date range (ISO 8601)"),
    to_date: Optional[datetime] = Query(default=None, description="End of date range (ISO 8601)"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    List email events for the authenticated account with optional filters.

    Designed for dashboard queries — filter by event type, contact, campaign,
    provider, date range, or recipient address.
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        query = db.query(EmailEvent).filter(EmailEvent.account_id == account_id)

        if event_type:
            query = query.filter(EmailEvent.event_type == event_type)

        if contact_id is not None:
            query = query.filter(EmailEvent.contact_id == contact_id)

        if campaign_id is not None:
            query = query.filter(EmailEvent.campaign_id == campaign_id)

        if tool_approval_id is not None:
            query = query.filter(EmailEvent.tool_approval_id == tool_approval_id)

        if primary_recipient:
            query = query.filter(EmailEvent.primary_recipient == primary_recipient.strip().lower())

        if provider:
            query = query.filter(EmailEvent.provider == provider)

        if from_date:
            query = query.filter(EmailEvent.created_at >= from_date)

        if to_date:
            query = query.filter(EmailEvent.created_at <= to_date)

        events = (
            query
            .order_by(EmailEvent.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        return events

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST EMAIL EVENTS]")


@router.get("/stats", response_model=EmailEventStatsResponse)
@limiter.limit("60/minute")
async def get_email_event_stats(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    campaign_id: Optional[int] = Query(default=None),
    tool_approval_id: Optional[int] = Query(default=None),
    from_date: Optional[datetime] = Query(default=None, description="Start of date range (ISO 8601)"),
    to_date: Optional[datetime] = Query(default=None, description="End of date range (ISO 8601)"),
):
    """
    Return aggregated event counts for the authenticated account.
    Supports the same date/campaign/approval filters as the list endpoint.
    Useful for summary cards on the email metrics dashboard.
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        from sqlalchemy import func as sqlfunc

        query = db.query(
            EmailEvent.event_type,
            sqlfunc.count(EmailEvent.id).label("count"),
        ).filter(EmailEvent.account_id == account_id)

        if campaign_id is not None:
            query = query.filter(EmailEvent.campaign_id == campaign_id)

        if tool_approval_id is not None:
            query = query.filter(EmailEvent.tool_approval_id == tool_approval_id)

        if from_date:
            query = query.filter(EmailEvent.created_at >= from_date)

        if to_date:
            query = query.filter(EmailEvent.created_at <= to_date)

        rows = query.group_by(EmailEvent.event_type).all()

        counts = {row.event_type: row.count for row in rows}
        total = sum(counts.values())

        return EmailEventStatsResponse(
            send=counts.get("send", 0),
            delivery=counts.get("delivery", 0),
            open=counts.get("open", 0),
            bounce=counts.get("bounce", 0),
            complaint=counts.get("complaint", 0),
            other=counts.get("other", 0),
            total=total,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[EMAIL EVENT STATS]")
