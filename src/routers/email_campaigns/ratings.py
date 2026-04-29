"""
Read-only endpoints for querying email campaign ratings.

GET /api/email-campaigns/{campaign_id}/ratings          — list ratings
GET /api/email-campaigns/{campaign_id}/ratings/summary  — aggregated stats
GET /api/email-campaigns/{campaign_id}/ratings/{rating_id} — single rating
"""
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func as sql_func

from src.deps import db_dependency, auth_dependency
from src.db.models import EmailCampaign, EmailCampaignRating
from src.rate_limit import limiter

router = APIRouter()


# ── Response Models ──────────────────────────────────────────────────────────

class RatingResponse(BaseModel):
    id: int
    campaign_id: Optional[int] = None
    email_template_id: Optional[int] = None
    contact_id: Optional[int] = None
    primary_recipient: Optional[str] = None
    tracking_id: str
    rating: int
    created_at: datetime

    class Config:
        from_attributes = True


class RatingSummaryResponse(BaseModel):
    campaign_id: int
    total_ratings: int
    average_rating: Optional[float] = None
    distribution: dict[int, int]
    by_template: dict[int, "TemplateSummary"]


class TemplateSummary(BaseModel):
    total_ratings: int
    average_rating: Optional[float] = None


# Rebuild model refs after forward-reference definition
RatingSummaryResponse.model_rebuild()


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/{campaign_id}/ratings", response_model=List[RatingResponse])
@limiter.limit("60/minute")
async def list_campaign_ratings(
    campaign_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    email_template_id: Optional[int] = Query(default=None, description="Filter by template"),
    contact_id: Optional[int] = Query(default=None, description="Filter by contact"),
    min_rating: Optional[int] = Query(default=None, ge=1, le=5, description="Minimum rating"),
    max_rating: Optional[int] = Query(default=None, ge=1, le=5, description="Maximum rating"),
    limit: int = Query(default=100, ge=1, le=500, description="Max results to return"),
    offset: int = Query(default=0, ge=0, description="Pagination offset"),
):
    """List all ratings for a campaign with optional filters."""
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

    campaign = db.query(EmailCampaign).filter(
        EmailCampaign.id == campaign_id,
        EmailCampaign.account_id == account_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")

    q = db.query(EmailCampaignRating).filter(
        EmailCampaignRating.campaign_id == campaign_id,
        EmailCampaignRating.account_id == account_id,
    )

    if email_template_id is not None:
        q = q.filter(EmailCampaignRating.email_template_id == email_template_id)
    if contact_id is not None:
        q = q.filter(EmailCampaignRating.contact_id == contact_id)
    if min_rating is not None:
        q = q.filter(EmailCampaignRating.rating >= min_rating)
    if max_rating is not None:
        q = q.filter(EmailCampaignRating.rating <= max_rating)

    return (
        q.order_by(EmailCampaignRating.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{campaign_id}/ratings/summary", response_model=RatingSummaryResponse)
@limiter.limit("60/minute")
async def campaign_ratings_summary(
    campaign_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Return aggregated rating statistics for a campaign."""
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

    campaign = db.query(EmailCampaign).filter(
        EmailCampaign.id == campaign_id,
        EmailCampaign.account_id == account_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")

    base_filter = [
        EmailCampaignRating.campaign_id == campaign_id,
        EmailCampaignRating.account_id == account_id,
    ]

    # Overall stats
    stats = db.query(
        sql_func.count(EmailCampaignRating.id),
        sql_func.avg(EmailCampaignRating.rating),
    ).filter(*base_filter).first()

    total_ratings = stats[0] or 0
    average_rating = round(float(stats[1]), 2) if stats[1] is not None else None

    # Distribution (1-5)
    dist_rows = (
        db.query(EmailCampaignRating.rating, sql_func.count(EmailCampaignRating.id))
        .filter(*base_filter)
        .group_by(EmailCampaignRating.rating)
        .all()
    )
    distribution = {i: 0 for i in range(1, 6)}
    for rating_val, count in dist_rows:
        distribution[rating_val] = count

    # Per-template breakdown
    template_rows = (
        db.query(
            EmailCampaignRating.email_template_id,
            sql_func.count(EmailCampaignRating.id),
            sql_func.avg(EmailCampaignRating.rating),
        )
        .filter(*base_filter, EmailCampaignRating.email_template_id.isnot(None))
        .group_by(EmailCampaignRating.email_template_id)
        .all()
    )
    by_template = {
        tmpl_id: TemplateSummary(
            total_ratings=count,
            average_rating=round(float(avg), 2) if avg is not None else None,
        )
        for tmpl_id, count, avg in template_rows
    }

    return RatingSummaryResponse(
        campaign_id=campaign_id,
        total_ratings=total_ratings,
        average_rating=average_rating,
        distribution=distribution,
        by_template=by_template,
    )


@router.get("/{campaign_id}/ratings/{rating_id}", response_model=RatingResponse)
@limiter.limit("60/minute")
async def get_campaign_rating(
    campaign_id: int,
    rating_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Get a single rating by ID within a campaign."""
    account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

    campaign = db.query(EmailCampaign).filter(
        EmailCampaign.id == campaign_id,
        EmailCampaign.account_id == account_id,
    ).first()
    if not campaign:
        raise HTTPException(status_code=404, detail="Email campaign not found")

    rating = db.query(EmailCampaignRating).filter(
        EmailCampaignRating.id == rating_id,
        EmailCampaignRating.campaign_id == campaign_id,
        EmailCampaignRating.account_id == account_id,
    ).first()
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")

    return rating
