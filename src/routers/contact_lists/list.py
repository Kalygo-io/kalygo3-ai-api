"""
List contact lists endpoint.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import ContactList, ContactListMember, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import ContactListSummaryResponse
from src.utils.errors import handle_db_error

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[ContactListSummaryResponse])
@limiter.limit("60/minute")
async def list_contact_lists(
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """List all contact lists for the authenticated account."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        contact_lists = (
            db.query(ContactList)
            .filter(ContactList.account_id == account_id)
            .order_by(ContactList.updated_at.desc())
            .all()
        )

        results = []
        for cl in contact_lists:
            count = (
                db.query(ContactListMember)
                .filter(ContactListMember.contact_list_id == cl.id)
                .count()
            )
            results.append(
                ContactListSummaryResponse(
                    id=cl.id,
                    account_id=cl.account_id,
                    name=cl.name,
                    description=cl.description,
                    member_count=count,
                    created_at=cl.created_at,
                    updated_at=cl.updated_at,
                )
            )

        return results

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST CONTACT LISTS]")
