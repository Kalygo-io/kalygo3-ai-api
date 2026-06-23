"""
List companies endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from sqlalchemy import func as sqlfunc
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import Company, CompanyContact

from .models import CompanyListResponse, CompanySummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/", response_model=CompanyListResponse)
@limiter.limit("60/minute")
async def list_companies(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
    search: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=500, description="Number of companies to return"),
    offset: int = Query(0, ge=0, description="Number of companies to skip"),
):
    """
    List companies for the authenticated account (server-side paginated).

    Supports full-text ?search= over name, domain, and industry. Returns a
    paginated envelope ({companies, total, limit, offset, has_more}).
    """
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

        query = db.query(Company).filter(Company.account_id == account_id)

        if search:
            term = f"%{search.lower()}%"
            query = query.filter(
                sqlfunc.lower(Company.name).like(term)
                | sqlfunc.lower(Company.domain).like(term)
                | sqlfunc.lower(Company.industry).like(term)
            )

        total = query.count()
        companies = (
            query.order_by(Company.updated_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

        results = []
        for company in companies:
            count = (
                db.query(CompanyContact)
                .filter(CompanyContact.company_id == company.id)
                .count()
            )
            results.append(
                CompanySummaryResponse(
                    id=company.id,
                    account_id=company.account_id,
                    name=company.name,
                    domain=company.domain,
                    website=company.website,
                    industry=company.industry,
                    description=company.description,
                    linkedin_url=company.linkedin_url,
                    contact_count=count,
                    created_at=company.created_at,
                    updated_at=company.updated_at,
                )
            )

        return CompanyListResponse(
            companies=results,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST COMPANIES]")
