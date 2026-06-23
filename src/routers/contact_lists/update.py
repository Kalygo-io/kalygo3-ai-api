"""
Update contact list endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency, account_id_from_claims, ensure_account
from src.db.models import ContactList, ContactListMember

from .models import UpdateContactListRequest, ContactListSummaryResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.put("/{list_id}", response_model=ContactListSummaryResponse)
@limiter.limit("30/minute")
async def update_contact_list(
    list_id: int,
    request_body: UpdateContactListRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = account_id_from_claims(auth)
        account = ensure_account(db, account_id)

        contact_list = db.query(ContactList).filter(
            ContactList.id == list_id,
            ContactList.account_id == account_id,
        ).first()

        if not contact_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found")

        if request_body.name is not None:
            if not request_body.name.strip():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="List name cannot be empty")
            contact_list.name = request_body.name.strip()

        if request_body.description is not None:
            contact_list.description = request_body.description or None

        db.commit()
        db.refresh(contact_list)

        count = (
            db.query(ContactListMember)
            .filter(ContactListMember.contact_list_id == contact_list.id)
            .count()
        )

        return ContactListSummaryResponse(
            id=contact_list.id,
            account_id=contact_list.account_id,
            name=contact_list.name,
            description=contact_list.description,
            member_count=count,
            created_at=contact_list.created_at,
            updated_at=contact_list.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE CONTACT LIST]")
