"""
Shared helpers for the vectorStores router.
"""
from fastapi import HTTPException, status
from src.db.models import VectorStore
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import get_credential_value
from src.services.credential_access import resolve_default_credential
from src.services.vector_store_credentials import resolve_index_pinecone_credential
from src.utils.errors import handle_db_error


def get_or_create_vector_store(db, owner_account_id: int, index_name: str) -> VectorStore:
    """
    Return the VectorStore row for (owner, index), creating it (with no explicit
    credential bindings → default fallback) if missing. Lets sharing/audit work
    for indexes created before the VectorStore table existed. Caller commits.
    """
    store = (
        db.query(VectorStore)
        .filter(
            VectorStore.owner_account_id == owner_account_id,
            VectorStore.index_name == index_name,
        )
        .first()
    )
    if store is None:
        store = VectorStore(owner_account_id=owner_account_id, index_name=index_name)
        db.add(store)
        db.flush()  # assign id for grant references in the same transaction
    return store


def _pinecone_key_from_credential(credential) -> str:
    if not credential:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pinecone API key not found. Please add your Pinecone API key in credentials."
        )
    try:
        return get_credential_value(credential, "api_key")
    except Exception as e:
        raise handle_db_error(e, "[DECRYPT PINECONE API KEY]")


def get_pinecone_api_key(db, account_id: int) -> str:
    """
    Retrieve and decrypt the account's DEFAULT Pinecone API key (owned or shared).

    Used by account-level operations that aren't scoped to a single index
    (e.g. listing all indexes, creating a new one). For operations on a specific
    knowledge base, prefer get_pinecone_api_key_for_index so an explicit
    per-index credential binding is honored.
    """
    credential = resolve_default_credential(db, account_id, ServiceName.PINECONE_API_KEY)
    return _pinecone_key_from_credential(credential)


def get_pinecone_api_key_for_index(db, owner_account_id: int, index_name: str) -> str:
    """
    Retrieve and decrypt the Pinecone API key for a specific knowledge base.

    Honors the VectorStore's explicit pinecone_credential binding when set,
    falling back to the owner's default Pinecone credential otherwise.
    """
    credential = resolve_index_pinecone_credential(db, owner_account_id, index_name)
    return _pinecone_key_from_credential(credential)
