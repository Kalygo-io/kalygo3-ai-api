"""
List ingestion logs for a specific index (delegation endpoint).
"""
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Request, Query
from src.deps import db_dependency, jwt_dependency
from src.rate_limit import limiter

router = APIRouter()

@router.get("/indexes/{index_name}/ingestion-logs")
@limiter.limit("30/minute")
async def list_index_ingestion_logs(
    index_name: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type (INGEST, DELETE, UPDATE)"),
    status: Optional[str] = Query(None, alias="status", description="Filter by status (SUCCESS, FAILED, PARTIAL, PENDING)"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    batch_number: Optional[str] = Query(None, description="Filter by batch number"),
    start_date: Optional[datetime] = Query(None, description="Filter logs created after this date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter logs created before this date (ISO format)"),
    limit: int = Query(50, ge=1, le=500, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
    owner_account_id: Optional[int] = Query(None, description="Owner of a shared knowledge base whose logs to read"),
):
    """
    List ingestion logs for a specific index.
    This endpoint filters logs by index_name automatically.
    """
    # Import here to avoid circular imports
    from .ingestion_logs import list_ingestion_logs

    return await list_ingestion_logs(
        db=db,
        jwt=jwt,
        request=request,
        index_name=index_name,
        namespace=namespace,
        operation_type=operation_type,
        status_filter=status,
        provider=provider,
        batch_number=batch_number,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset,
        owner_account_id=owner_account_id,
    )
