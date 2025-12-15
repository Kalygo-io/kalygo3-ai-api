"""
Ingestion Logs router for reading VectorDbIngestionLog entries.
Provides endpoints to query and filter vector database operation logs.
"""
from fastapi import APIRouter, HTTPException, status, Request, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from src.deps import db_dependency, jwt_dependency
from src.db.models import VectorDbIngestionLog, Account, OperationType, OperationStatus
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy import and_, or_

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()


class IngestionLogResponse(BaseModel):
    """Response model for ingestion log entries."""
    id: str
    created_at: str
    operation_type: str
    status: str
    account_id: int
    provider: str
    index_name: str
    namespace: Optional[str] = None
    filenames: Optional[List[str]] = None
    comment: Optional[str] = None
    vectors_added: int
    vectors_deleted: int
    vectors_failed: int
    error_message: Optional[str] = None
    error_code: Optional[str] = None
    batch_number: Optional[str] = None

    class Config:
        from_attributes = True


class IngestionLogsListResponse(BaseModel):
    """Response model for paginated ingestion logs list."""
    logs: List[IngestionLogResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


@router.get("/ingestion-logs", response_model=IngestionLogsListResponse)
@limiter.limit("30/minute")
async def list_ingestion_logs(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    # Filter parameters
    index_name: Optional[str] = Query(None, description="Filter by index name"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
    operation_type: Optional[str] = Query(None, description="Filter by operation type (INGEST, DELETE, UPDATE)"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (SUCCESS, FAILED, PARTIAL, PENDING)"),
    provider: Optional[str] = Query(None, description="Filter by provider"),
    batch_number: Optional[str] = Query(None, description="Filter by batch number"),
    # Date range filters
    start_date: Optional[datetime] = Query(None, description="Filter logs created after this date (ISO format)"),
    end_date: Optional[datetime] = Query(None, description="Filter logs created before this date (ISO format)"),
    # Pagination
    limit: int = Query(50, ge=1, le=500, description="Number of logs to return"),
    offset: int = Query(0, ge=0, description="Number of logs to skip"),
):
    """
    List ingestion logs for the authenticated user with optional filtering.
    
    Supports filtering by:
    - index_name: Filter by specific index
    - namespace: Filter by namespace
    - operation_type: INGEST, DELETE, or UPDATE
    - status: SUCCESS, FAILED, PARTIAL, or PENDING
    - provider: Filter by provider (e.g., 'pinecone')
    - batch_number: Filter by batch UUID
    - start_date/end_date: Filter by date range
    
    Results are paginated and ordered by created_at descending (newest first).
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Start with base query filtered by account_id
        query = db.query(VectorDbIngestionLog).filter(
            VectorDbIngestionLog.account_id == account_id
        )
        
        # Apply filters
        if index_name:
            query = query.filter(VectorDbIngestionLog.index_name == index_name)
        
        if namespace:
            query = query.filter(VectorDbIngestionLog.namespace == namespace)
        
        if operation_type:
            # Validate and convert operation_type string to enum
            try:
                op_type_enum = OperationType(operation_type.upper())
                query = query.filter(VectorDbIngestionLog.operation_type == op_type_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid operation_type: {operation_type}. Must be one of: {[e.value for e in OperationType]}"
                )
        
        if status_filter:
            # Validate and convert status string to enum
            try:
                status_enum = OperationStatus(status_filter.upper())
                query = query.filter(VectorDbIngestionLog.status == status_enum)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status_filter}. Must be one of: {[e.value for e in OperationStatus]}"
                )
        
        if provider:
            query = query.filter(VectorDbIngestionLog.provider == provider)
        
        if batch_number:
            query = query.filter(VectorDbIngestionLog.batch_number == batch_number)
        
        if start_date:
            query = query.filter(VectorDbIngestionLog.created_at >= start_date)
        
        if end_date:
            query = query.filter(VectorDbIngestionLog.created_at <= end_date)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply ordering and pagination
        logs = query.order_by(VectorDbIngestionLog.created_at.desc()).offset(offset).limit(limit).all()
        
        # Convert to response models
        log_responses = []
        for log in logs:
            # Handle enum values (PostgreSQL enums return strings)
            operation_type_str = str(log.operation_type)
            status_str = str(log.status)
            
            log_responses.append(
                IngestionLogResponse(
                    id=str(log.id),
                    created_at=log.created_at.isoformat(),
                    operation_type=operation_type_str,
                    status=status_str,
                    account_id=log.account_id,
                    provider=log.provider,
                    index_name=log.index_name,
                    namespace=log.namespace,
                    filenames=log.filenames if isinstance(log.filenames, list) else None,
                    comment=log.comment,
                    vectors_added=log.vectors_added,
                    vectors_deleted=log.vectors_deleted,
                    vectors_failed=log.vectors_failed,
                    error_message=log.error_message,
                    error_code=log.error_code,
                    batch_number=log.batch_number
                )
            )
        
        return IngestionLogsListResponse(
            logs=log_responses,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + limit) < total
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error listing ingestion logs: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while listing ingestion logs: {str(e)}"
        )


@router.get("/ingestion-logs/{log_id}", response_model=IngestionLogResponse)
@limiter.limit("30/minute")
async def get_ingestion_log(
    log_id: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a specific ingestion log entry by ID.
    Only returns logs belonging to the authenticated user.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Query log by ID and account_id
        log = db.query(VectorDbIngestionLog).filter(
            VectorDbIngestionLog.id == log_id,
            VectorDbIngestionLog.account_id == account_id
        ).first()
        
        if not log:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingestion log not found"
            )
        
        # Handle enum values (PostgreSQL enums return strings)
        operation_type_str = str(log.operation_type)
        status_str = str(log.status)
        
        return IngestionLogResponse(
            id=str(log.id),
            created_at=log.created_at.isoformat(),
            operation_type=operation_type_str,
            status=status_str,
            account_id=log.account_id,
            provider=log.provider,
            index_name=log.index_name,
            namespace=log.namespace,
            filenames=log.filenames if isinstance(log.filenames, list) else None,
            comment=log.comment,
            vectors_added=log.vectors_added,
            vectors_deleted=log.vectors_deleted,
            vectors_failed=log.vectors_failed,
            error_message=log.error_message,
            error_code=log.error_code,
            batch_number=log.batch_number
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error retrieving ingestion log: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving ingestion log: {str(e)}"
        )


@router.get("/ingestion-logs/stats/summary", response_model=dict)
@limiter.limit("30/minute")
async def get_ingestion_logs_summary(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    index_name: Optional[str] = Query(None, description="Filter by index name"),
    namespace: Optional[str] = Query(None, description="Filter by namespace"),
):
    """
    Get summary statistics for ingestion logs.
    Returns aggregated counts and totals for the authenticated user's logs.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Base query
        query = db.query(VectorDbIngestionLog).filter(
            VectorDbIngestionLog.account_id == account_id
        )
        
        # Apply filters
        if index_name:
            query = query.filter(VectorDbIngestionLog.index_name == index_name)
        
        if namespace:
            query = query.filter(VectorDbIngestionLog.namespace == namespace)
        
        # Get all logs for aggregation
        logs = query.all()
        
        # Calculate statistics
        total_logs = len(logs)
        total_vectors_added = sum(log.vectors_added for log in logs)
        total_vectors_deleted = sum(log.vectors_deleted for log in logs)
        total_vectors_failed = sum(log.vectors_failed for log in logs)
        
        # Count by operation type
        operation_type_counts = {}
        for op_type in OperationType:
            operation_type_counts[op_type.value] = sum(
                1 for log in logs 
                if str(log.operation_type) == op_type.value
            )
        
        # Count by status
        status_counts = {}
        for stat in OperationStatus:
            status_counts[stat.value] = sum(
                1 for log in logs 
                if str(log.status) == stat.value
            )
        
        # Count by provider
        provider_counts = {}
        for log in logs:
            provider_counts[log.provider] = provider_counts.get(log.provider, 0) + 1
        
        # Count by index
        index_counts = {}
        for log in logs:
            index_counts[log.index_name] = index_counts.get(log.index_name, 0) + 1
        
        return {
            "total_logs": total_logs,
            "total_vectors_added": total_vectors_added,
            "total_vectors_deleted": total_vectors_deleted,
            "total_vectors_failed": total_vectors_failed,
            "operation_type_counts": operation_type_counts,
            "status_counts": status_counts,
            "provider_counts": provider_counts,
            "index_counts": index_counts,
            "filters_applied": {
                "index_name": index_name,
                "namespace": namespace
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting ingestion logs summary: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while getting ingestion logs summary: {str(e)}"
        )

