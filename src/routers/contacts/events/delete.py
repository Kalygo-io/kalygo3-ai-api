"""
Delete a contact event endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, auth_dependency
from src.db.models import Contact, ContactEvent, Account
from slowapi import Limiter
from slowapi.util import get_remote_address
from src.utils.errors import handle_db_error
from src.services.crm_vector_service import delete_vector

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_contact_event(
    contact_id: int,
    event_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        account = db.query(Account).filter(Account.id == account_id).first()

        if not account:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

        contact = db.query(Contact).filter(
            Contact.id == contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        event = db.query(ContactEvent).filter(
            ContactEvent.id == event_id,
            ContactEvent.contact_id == contact_id,
        ).first()

        if not event:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

        db.delete(event)
        db.commit()

        try:
            delete_vector(f"contact_event_{event_id}")
        except Exception as vec_err:
            print(f"[DELETE CONTACT EVENT] Warning: vector delete failed: {vec_err}")

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE CONTACT EVENT]")
