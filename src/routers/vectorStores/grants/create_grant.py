"""
Grant a group or individual access to a knowledge base (index owner only).

Writes a unified AccessGrant (resource_type='vector_store', role 'read'|'write')
keyed by the VectorStore row id.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims
from src.db.models import AccessGrant
from src.services import access
from src.services.access_admin import resolve_principal, upsert_grant, record_access_event
from ..helpers import get_or_create_vector_store
from .models import CreateVectorStoreGrantRequest, VectorStoreAccessGrantResponse
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
    Share one of your knowledge bases with a group or individual.

    You can only share an index reachable by your own Pinecone key (you are the
    owner). role 'read' = view; 'write' = ingest/edit. For a group target you must
    own or co-administer the group.
    """
    try:
        account_id = account_id_from_claims(jwt)
        index_name = body.index_name.strip()
        if not index_name:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="index_name is required")

        principal_type, principal_id, label = resolve_principal(
            db,
            caller_account_id=account_id,
            access_group_id=body.accessGroupId,
            grantee_email=body.granteeEmail,
        )

        store = get_or_create_vector_store(db, account_id, index_name)

        existing = db.query(AccessGrant).filter(
            AccessGrant.principal_type == principal_type,
            AccessGrant.principal_id == principal_id,
            AccessGrant.resource_type == access.VECTOR_STORE,
            AccessGrant.resource_id == store.id,
        ).first()
        if existing and existing.role == body.role:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Grant already exists for this principal")

        grant = upsert_grant(
            db,
            principal_type=principal_type,
            principal_id=principal_id,
            resource_type=access.VECTOR_STORE,
            resource_id=store.id,
            role=body.role,
        )
        record_access_event(
            db,
            event_type="role_change" if existing else "create",
            actor_account_id=account_id,
            resource_type=access.VECTOR_STORE,
            resource_id=store.id,
            principal_type=principal_type,
            principal_id=principal_id,
            role=body.role,
        )
        db.commit()
        db.refresh(grant)

        return VectorStoreAccessGrantResponse(
            id=grant.id,
            owner_account_id=account_id,
            index_name=index_name,
            access_group_id=principal_id if principal_type == access.GROUP else None,
            grantee_account_id=principal_id if principal_type == access.ACCOUNT else None,
            label=label,
            target_type="group" if principal_type == access.GROUP else "individual",
            role=grant.role,
            created_at=grant.created_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CREATE VS GRANT]")
