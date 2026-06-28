"""
Index-scoped credential resolution for knowledge bases (vector stores).

A knowledge base (Pinecone index) can bind its Pinecone and GCS credentials
EXPLICITLY via a VectorStore row. When a binding is set and usable, that exact
credential is used — no drift if the owner later changes account defaults. When a
binding is null (e.g. a backfilled pre-existing index, or one whose bound
credential was deleted), we fall back to the owner's default for that type.

CANONICAL FILE. Mirrored byte-for-byte into kalygo3-agent-api
(src/services/vector_store_credentials.py) via the repo-root sync scripts. Edit
the ai-api copy, then run ./sync-schemas.sh. Do not edit the two copies
independently.
"""
from sqlalchemy.orm import Session

from src.db.models import Credential, VectorStore
from src.db.service_name import ServiceName
from src.services.credential_access import (
    can_use_credential,
    resolve_default_credential,
)


def _get_store(db: Session, owner_account_id: int, index_name: str):
    return (
        db.query(VectorStore)
        .filter(
            VectorStore.owner_account_id == owner_account_id,
            VectorStore.index_name == index_name,
        )
        .first()
    )


def _resolve(db: Session, owner_account_id: int, index_name: str, bound_id, cred_type):
    """Explicit binding if set & usable by the owner, else the owner's default."""
    if bound_id is not None and can_use_credential(db, owner_account_id, bound_id):
        return db.query(Credential).filter(Credential.id == bound_id).first()
    return resolve_default_credential(db, owner_account_id, cred_type)


def resolve_index_pinecone_credential(
    db: Session, owner_account_id: int, index_name: str
) -> "Credential | None":
    """Pinecone credential for (owner, index): explicit binding, else default."""
    store = _get_store(db, owner_account_id, index_name)
    bound_id = store.pinecone_credential_id if store else None
    return _resolve(db, owner_account_id, index_name, bound_id, ServiceName.PINECONE_API_KEY)


def resolve_index_gcs_credential(
    db: Session, owner_account_id: int, index_name: str
) -> "Credential | None":
    """GCS credential for (owner, index): explicit binding, else default."""
    store = _get_store(db, owner_account_id, index_name)
    bound_id = store.gcs_credential_id if store else None
    return _resolve(db, owner_account_id, index_name, bound_id, ServiceName.GOOGLE_CLOUD_STORAGE)
