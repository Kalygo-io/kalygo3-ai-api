"""
Contact list members sub-router — add/remove/list contacts within a list.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from sqlalchemy.exc import IntegrityError
from src.deps import db_dependency, auth_dependency
from src.db.models import ContactList, ContactListMember, Contact

from src.routers.contact_lists.models import (
    ContactListMemberResponse,
    AddContactToListRequest,
    BulkAddContactsToListRequest,
)
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

@router.get("/", response_model=List[ContactListMemberResponse])
@limiter.limit("60/minute")
async def list_members(
    list_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """List all contacts in a given contact list."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact_list = db.query(ContactList).filter(
            ContactList.id == list_id,
            ContactList.account_id == account_id,
        ).first()

        if not contact_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found")

        members = (
            db.query(ContactListMember)
            .filter(ContactListMember.contact_list_id == list_id)
            .all()
        )
        return members

    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST MEMBERS]")

@router.post("/", status_code=status.HTTP_201_CREATED, response_model=ContactListMemberResponse)
@limiter.limit("60/minute")
async def add_member(
    list_id: int,
    request_body: AddContactToListRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Add a single contact to a contact list."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact_list = db.query(ContactList).filter(
            ContactList.id == list_id,
            ContactList.account_id == account_id,
        ).first()

        if not contact_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found")

        contact = db.query(Contact).filter(
            Contact.id == request_body.contact_id,
            Contact.account_id == account_id,
        ).first()

        if not contact:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

        member = ContactListMember(
            contact_list_id=list_id,
            contact_id=request_body.contact_id,
            account_id=account_id,
        )
        db.add(member)
        db.commit()
        db.refresh(member)

        return member

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Contact is already a member of this list",
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[ADD MEMBER]")

@router.post("/bulk", status_code=status.HTTP_200_OK)
@limiter.limit("30/minute")
async def bulk_add_members(
    list_id: int,
    request_body: BulkAddContactsToListRequest,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Add multiple contacts to a list in one call, skipping duplicates."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact_list = db.query(ContactList).filter(
            ContactList.id == list_id,
            ContactList.account_id == account_id,
        ).first()

        if not contact_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found")

        existing_ids = {
            m.contact_id
            for m in db.query(ContactListMember)
            .filter(ContactListMember.contact_list_id == list_id)
            .all()
        }

        valid_contacts = db.query(Contact).filter(
            Contact.id.in_(request_body.contact_ids),
            Contact.account_id == account_id,
        ).all()
        valid_ids = {c.id for c in valid_contacts}

        added = 0
        for contact_id in request_body.contact_ids:
            if contact_id in valid_ids and contact_id not in existing_ids:
                db.add(ContactListMember(
                    contact_list_id=list_id,
                    contact_id=contact_id,
                    account_id=account_id,
                ))
                added += 1

        db.commit()
        return {"added": added, "skipped": len(request_body.contact_ids) - added}

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[BULK ADD MEMBERS]")

@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("60/minute")
async def remove_member(
    list_id: int,
    contact_id: int,
    db: db_dependency,
    auth: auth_dependency,
    request: Request,
):
    """Remove a contact from a contact list."""
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        contact_list = db.query(ContactList).filter(
            ContactList.id == list_id,
            ContactList.account_id == account_id,
        ).first()

        if not contact_list:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact list not found")

        member = db.query(ContactListMember).filter(
            ContactListMember.contact_list_id == list_id,
            ContactListMember.contact_id == contact_id,
        ).first()

        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact is not a member of this list")

        db.delete(member)
        db.commit()

        return None

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[REMOVE MEMBER]")
