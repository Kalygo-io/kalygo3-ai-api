"""
Update company endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import Company, CompanyContact

from .models import UpdateCompanyRequest, CompanySummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.put("/{company_id}", response_model=CompanySummaryResponse)
@limiter.limit("30/minute")
async def update_company(
    company_id: int,
    request_body: UpdateCompanyRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

        company = db.query(Company).filter(
            Company.id == company_id,
            Company.account_id == account_id,
        ).first()

        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

        if request_body.name is not None:
            if not request_body.name.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Company name cannot be empty")
            company.name = request_body.name.strip()

        if request_body.domain is not None:
            company.domain = request_body.domain or None
        if request_body.website is not None:
            company.website = request_body.website or None
        if request_body.industry is not None:
            company.industry = request_body.industry or None
        if request_body.description is not None:
            company.description = request_body.description or None
        if request_body.linkedin_url is not None:
            company.linkedin_url = request_body.linkedin_url or None

        db.commit()
        db.refresh(company)

        count = (
            db.query(CompanyContact)
            .filter(CompanyContact.company_id == company.id)
            .count()
        )

        return CompanySummaryResponse(
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

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE COMPANY]")
