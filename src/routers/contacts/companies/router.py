"""
Contact companies sub-router — associate / disassociate a contact with companies.

This is the reverse view of the company → contacts association, operating on the
same company_contacts join table (CompanyContact). It powers the "Companies"
section on the contact detail page.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy.exc import IntegrityError
from src.deps import db_dependency, auth_dependency
from src.db.models import Company, CompanyContact, Contact

from .models import AddCompanyToContactRequest, ContactCompanyResponse
from src.routers.companies.models import CompanySummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


def _to_response(membership: CompanyContact, db) -> ContactCompanyResponse:
    """Build the response, computing the company's total contact_count."""
    company = membership.company
    count = (
        db.query(CompanyContact)
        .filter(CompanyContact.company_id == company.id)
        .count()
    )
    return ContactCompanyResponse(
        id=membership.id,
        company_id=membership.company_id,
        contact_id=membership.contact_id,
        account_id=membership.account_id,
        title=membership.title,
        added_at=membership.added_at,
        company=CompanySummaryResponse(
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
        ),
    )


@router.get("/", response_model=List[ContactCompanyResponse])
@limiter.limit("60/minute")
async def list_contact_companies(
    contact_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """List all companies a given contact is associated with."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        memberships = (
            db.query(CompanyContact)
            .filter(CompanyContact.contact_id == contact_id)
            .all()
        )
        return [_to_response(m, db) for m in memberships]

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CONTACT COMPANIES]")


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactCompanyResponse)
@limiter.limit("60/minute")
async def add_contact_company(
    contact_id: int,
    request_body: AddCompanyToContactRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Associate a contact with a company."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        company = db.query(Company).filter(
            Company.id == request_body.company_id,
            Company.account_id == account_id,
        ).first()

        if not company:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Company not found")

        membership = CompanyContact(
            company_id=request_body.company_id,
            contact_id=contact_id,
            account_id=account_id,
            title=request_body.title,
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)

        return _to_response(membership, db)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact is already associated with this company",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ADD CONTACT COMPANY]")


@router.delete("/{company_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def remove_contact_company(
    contact_id: int,
    company_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Disassociate a contact from a company."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        membership = db.query(CompanyContact).filter(
            CompanyContact.contact_id == contact_id,
            CompanyContact.company_id == company_id,
        ).first()

        if not membership:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact is not associated with this company")

        db.delete(membership)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REMOVE CONTACT COMPANY]")
