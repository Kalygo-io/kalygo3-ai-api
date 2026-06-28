"""
List access grants for a knowledge base (index owner only). Reads AccessGrant.
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import VectorStore, AccessGrant
from src.services import access
from src.services.access_admin import grant_label
from .models import VectorStoreAccessGrantResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.get("/grants", response_model=List[VectorStoreAccessGrantResponse])
@limiter.limit("30/minute")
async def list_grants(
    index_name: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """List who a knowledge base is shared with (groups + individuals). Index owner only."""
    try:
        account_id = account_id_from_claims(jwt)
        index_name = index_name.strip()

        store = db.query(VectorStore).filter(
            VectorStore.owner_account_id == account_id,
            VectorStore.index_name == index_name,
        ).first()
        if not store:
            return []

        grants = (
            db.query(AccessGrant)
            .filter(
                AccessGrant.resource_type == access.VECTOR_STORE,
                AccessGrant.resource_id == store.id,
            )
            .order_by(AccessGrant.created_at.desc())
            .all()
        )

        return [
            VectorStoreAccessGrantResponse(
                id=g.id,
                owner_account_id=account_id,
                index_name=index_name,
                access_group_id=g.principal_id if g.principal_type == access.GROUP else None,
                grantee_account_id=g.principal_id if g.principal_type == access.ACCOUNT else None,
                label=grant_label(db, g),
                target_type="group" if g.principal_type == access.GROUP else "individual",
                role=g.role,
                created_at=g.created_at,
            )
            for g in grants
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST VS GRANTS]")
