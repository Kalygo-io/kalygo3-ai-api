"""
Grant an access group access to a knowledge base (index owner only).
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGroup, VectorStoreAccessGrant
from .models import CreateVectorStoreGrantRequest, VectorStoreAccessGrantResponse
from src.services.access_group_roles import is_group_manager
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()


@router.post("/grants", response_model=VectorStoreAccessGrantResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_grant(
    body: CreateVectorStoreGrantRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
):
    """
    Grant an access group access to one of your knowledge bases.

    The grant always names the caller as the index owner — you can only share an
    index reachable by your own Pinecone key. The caller must own or co-administer
    the target access group. Shared members get read access; group admins get
    write (ingest/edit).
    """
    try:
        account_id = account_id_from_claims(jwt)
        index_name = body.index_name.strip()
        if not index_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="index_name is required")

        group = db.query(AccessGroup).filter(AccessGroup.id == body.accessGroupId).first()
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access group not found")
        if not is_group_manager(db, group, account_id):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You do not have permission to manage this group")

        existing = db.query(VectorStoreAccessGrant).filter(
            VectorStoreAccessGrant.owner_account_id == account_id,
            VectorStoreAccessGrant.index_name == index_name,
            VectorStoreAccessGrant.access_group_id == body.accessGroupId,
        ).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Grant already exists for this group")

        grant = VectorStoreAccessGrant(
            owner_account_id=account_id,
            index_name=index_name,
            access_group_id=body.accessGroupId,
        )
        db.add(grant)
        db.commit()
        db.refresh(grant)

        return VectorStoreAccessGrantResponse(
            id=grant.id,
            owner_account_id=grant.owner_account_id,
            index_name=grant.index_name,
            access_group_id=grant.access_group_id,
            access_group_name=group.name,
            created_at=grant.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE VS GRANT]")
