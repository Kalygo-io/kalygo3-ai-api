"""
Create contact list endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import ContactList, Account

from .models import CreateContactListRequest, ContactListSummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactListSummaryResponse)
@limiter.limit("30/minute")
async def create_contact_list(
    request_body: CreateContactListRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        if not request_body.name or not request_body.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="List name cannot be empty")

        contact_list = ContactList(
            account_id=account_id,
            name=request_body.name.strip(),
            description=request_body.description,
        )

        db.add(contact_list)
        db.commit()
        db.refresh(contact_list)

        result = ContactListSummaryResponse(
            id=contact_list.id,
            account_id=contact_list.account_id,
            name=contact_list.name,
            description=contact_list.description,
            member_count=0,
            created_at=contact_list.created_at,
            updated_at=contact_list.updated_at,
        )
        return result

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE CONTACT LIST]")
