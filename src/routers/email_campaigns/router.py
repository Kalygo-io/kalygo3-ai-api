"""Email campaigns CRUD router."""
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Request, Query
from src.deps import db_dependency, auth_dependency
from src.db.models import EmailCampaign, EmailTemplate, ContactList
from src.utils.errors import handle_db_error

from .models import (
    CreateEmailCampaignRequest,
    UpdateEmailCampaignRequest,
    EmailCampaignResponse,
)
from src.rate_limit import limiter

router = APIRouter()


@router.get("/", response_model=List[EmailCampaignResponse])
@limiter.limit("60/minute")
async def list_email_campaigns(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    search: Optional[str] = Query(default=None, description="Filter by name (case-insensitive substring)"),
    status_filter: Optional[str] = Query(
        default=None, alias="status",
        description="Filter by campaign status (draft, active, paused, completed)"),
):
    try:
        account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
        q = db.query(EmailCampaign).filter(EmailCampaign.account_id == account_id)
        if search:
            q = q.filter(EmailCampaign.name.ilike(f"%{search}%"))
        if status_filter:
            q = q.filter(EmailCampaign.status == status_filter)
        return q.order_by(EmailCampaign.created_at.desc()).all()
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST EMAIL CAMPAIGNS]")


@router.get("/{campaign_id}", response_model=EmailCampaignResponse)
@limiter.limit("60/minute")
async def get_email_campaign(
    campaign_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id,
            EmailCampaign.account_id == account_id,
        ).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Email campaign not found")
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET EMAIL CAMPAIGN]")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=EmailCampaignResponse)
@limiter.limit("60/minute")
async def create_email_campaign(
    body: CreateEmailCampaignRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]

        if body.email_template_id is not None:
            tmpl = db.query(EmailTemplate).filter(
                EmailTemplate.id == body.email_template_id,
                EmailTemplate.account_id == account_id,
            ).first()
            if not tmpl:
                raise HTTPException(status_code=404, detail="Email template not found")

        if body.contact_list_id is not None:
            cl = db.query(ContactList).filter(
                ContactList.id == body.contact_list_id,
                ContactList.account_id == account_id,
            ).first()
            if not cl:
                raise HTTPException(status_code=404, detail="Contact list not found")

        campaign = EmailCampaign(
            account_id=account_id,
            name=body.name,
            description=body.description,
            email_template_id=body.email_template_id,
            contact_list_id=body.contact_list_id,
            status=body.status or "draft",
        )
        db.add(campaign)
        db.commit()
        db.refresh(campaign)
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE EMAIL CAMPAIGN]")


@router.patch("/{campaign_id}", response_model=EmailCampaignResponse)
@limiter.limit("60/minute")
async def update_email_campaign(
    campaign_id: int,
    body: UpdateEmailCampaignRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id,
            EmailCampaign.account_id == account_id,
        ).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Email campaign not found")

        if body.email_template_id is not None:
            tmpl = db.query(EmailTemplate).filter(
                EmailTemplate.id == body.email_template_id,
                EmailTemplate.account_id == account_id,
            ).first()
            if not tmpl:
                raise HTTPException(status_code=404, detail="Email template not found")

        if body.contact_list_id is not None:
            cl = db.query(ContactList).filter(
                ContactList.id == body.contact_list_id,
                ContactList.account_id == account_id,
            ).first()
            if not cl:
                raise HTTPException(status_code=404, detail="Contact list not found")

        if body.name is not None:
            campaign.name = body.name
        if body.description is not None:
            campaign.description = body.description
        if body.email_template_id is not None:
            campaign.email_template_id = body.email_template_id
        if body.contact_list_id is not None:
            campaign.contact_list_id = body.contact_list_id
        if body.status is not None:
            campaign.status = body.status

        db.commit()
        db.refresh(campaign)
        return campaign
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE EMAIL CAMPAIGN]")


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def delete_email_campaign(
    campaign_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth["id"]) if isinstance(auth["id"], str) else auth["id"]
        campaign = db.query(EmailCampaign).filter(
            EmailCampaign.id == campaign_id,
            EmailCampaign.account_id == account_id,
        ).first()
        if not campaign:
            raise HTTPException(status_code=404, detail="Email campaign not found")
        db.delete(campaign)
        db.commit()
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE EMAIL CAMPAIGN]")
