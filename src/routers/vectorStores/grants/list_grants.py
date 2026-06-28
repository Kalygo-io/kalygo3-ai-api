"""
List access grants for a knowledge base (index owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from typing import List
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, VectorStoreAccessGrant
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
    """List the access groups a knowledge base is shared with. Index owner only."""
    try:
        account_id = account_id_from_claims(jwt)

        rows = (
            db.query(VectorStoreAccessGrant, AccessGroup.name)
            .join(AccessGroup, AccessGroup.id == VectorStoreAccessGrant.access_group_id)
            .filter(
                VectorStoreAccessGrant.owner_account_id == account_id,
                VectorStoreAccessGrant.index_name == index_name.strip(),
            )
            .order_by(VectorStoreAccessGrant.created_at.desc())
            .all()
        )

        return [
            VectorStoreAccessGrantResponse(
                id=grant.id,
                owner_account_id=grant.owner_account_id,
                index_name=grant.index_name,
                access_group_id=grant.access_group_id,
                access_group_name=group_name,
                created_at=grant.created_at,
            )
            for grant, group_name in rows
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST VS GRANTS]")
