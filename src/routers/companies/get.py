"""
Get single company endpoint (includes full list of associated contacts).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Company, Account

from .models import CompanyResponse, CompanyContactResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/{company_id}", response_model=CompanyResponse)
@limiter.limit("60/minute")
async def get_company(
    company_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        company = db.query(Company).filter(
            Company.id == company_id,
            Company.account_id == account_id,
        ).first()

        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

        # The ORM relationship is `contact_memberships` (CompanyContact join
        # rows); map it onto the response's `contacts` field explicitly.
        return CompanyResponse(
            id=company.id,
            account_id=company.account_id,
            name=company.name,
            domain=company.domain,
            website=company.website,
            industry=company.industry,
            description=company.description,
            linkedin_url=company.linkedin_url,
            created_at=company.created_at,
            updated_at=company.updated_at,
            contacts=[
                CompanyContactResponse.model_validate(m)
                for m in company.contact_memberships
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[GET COMPANY]")
