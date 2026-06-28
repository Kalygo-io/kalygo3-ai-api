"""
Source-document signed-URL endpoint (agent-scoped).

A vector-search result points back to the original source file in GCS. When the
agent (and therefore its knowledge base) is SHARED with an account via an access
group, that member must be able to open the source — but they hold no GCS
credential and the file lives in the OWNER's bucket. This endpoint signs the URL
with the owner's key, authorized by the member's access to the agent.

Security model (defense in depth — the signed URL is the only thing the member
ever receives; the credential never leaves the server):
  1. The caller must be able to access the agent (can_access_agent).
  2. The owner is the agent's owner; signing uses the owner's GCS credential.
  3. The requested object path MUST appear in the owner's ingestion log for an
     index the agent actually searches. This prevents an authorized member from
     signing arbitrary objects in the owner's bucket.
  4. The bucket is the one RECORDED at ingest (not the owner's current default),
     so source files stay reachable even if the owner later swaps GCS credentials.
"""
import logging

from fastapi import APIRouter, Request, Query, HTTPException, status

from src.deps import jwt_dependency, db_dependency, account_id_from_claims, ensure_account
from src.db.models import Agent, VectorDbIngestionLog
from src.services.agent_access import can_access_agent
from src.services import account_gcs_service
from src.services.account_gcs_service import AccountGcsCredentialMissing
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Tool types that reference a vector index whose sources this endpoint can serve.
_VECTOR_TOOL_TYPES = {"vectorSearch", "vectorSearchWithReranking"}


def _agent_index_names(agent: Agent) -> set:
    """Index names referenced by the agent's vector-search tools."""
    config = agent.config or {}
    tools = (config.get("data") or {}).get("tools") or []
    names = set()
    for tool in tools:
        if isinstance(tool, dict) and tool.get("type") in _VECTOR_TOOL_TYPES:
            index = tool.get("index")
            if index:
                names.add(index)
    return names


@router.get("/source-url")
@limiter.limit("120/minute")
async def get_source_url(
    request: Request,
    agent_id: int = Query(..., description="Agent the source was retrieved through"),
    path: str = Query(..., description="Object path of the source file (bucket-relative)"),
    expires: int = Query(900, ge=60, le=3600, description="URL lifetime in seconds"),
    db: db_dependency = None,
    decoded_jwt: jwt_dependency = None,
):
    """Return a short-lived signed GET URL for an agent's source document."""
    try:
        account_id = account_id_from_claims(decoded_jwt)
        ensure_account(db, account_id)

        if not path or not path.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A path is required")
        path = path.strip()

        # 1. Access check (owner or shared-via-group both pass here).
        if not can_access_agent(db, account_id, agent_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")

        owner_account_id = agent.account_id
        index_names = _agent_index_names(agent)
        if not index_names:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found")

        # 3. Path validation: the object must have been ingested into one of the
        #    agent's indexes by the owner. Also yields the recorded bucket (4).
        row = (
            db.query(VectorDbIngestionLog)
            .filter(
                VectorDbIngestionLog.account_id == owner_account_id,
                VectorDbIngestionLog.gcs_file_path == path,
                VectorDbIngestionLog.index_name.in_(index_names),
                VectorDbIngestionLog.gcs_bucket.isnot(None),
            )
            .order_by(VectorDbIngestionLog.created_at.desc())
            .first()
        )
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source document not found")

        try:
            url = account_gcs_service.generate_signed_url_for(
                db,
                owner_account_id,
                gcs_bucket=row.gcs_bucket,
                gcs_file_path=path,
                expiration_seconds=expires,
            )
        except AccountGcsCredentialMissing as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

        return {"url": url, "expires_in": expires}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("[FILES SOURCE URL] Unexpected error")
        raise handle_db_error(e, "[FILES SOURCE URL]")
