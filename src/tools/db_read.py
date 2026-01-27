"""
Database Read Tool

Provides read access to specified database tables.
Allows agents to query structured data from the Kalygo database.
"""
from typing import Dict, Any, Optional, List, TypedDict
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text
from src.db.models import (
    Account, 
    ChatAppSession, 
    ChatAppMessage,
    UsageCredits,
    VectorDbIngestionLog,
    ApiKey
)


# Type definitions for database read results
class DbReadResult(TypedDict):
    """A single row from database query."""
    data: Dict[str, Any]


class DbReadSuccess(TypedDict):
    """Successful database read result."""
    results: List[DbReadResult]
    table: str
    count: int


class DbReadError(TypedDict):
    """Error result from database read."""
    error: str


# Whitelist of tables that can be queried by agents
# Maps table names to their SQLAlchemy models
ALLOWED_TABLES = {
    "chat_app_sessions": ChatAppSession,
    "chat_app_messages": ChatAppMessage,
    "usage_credits": UsageCredits,
    "vector_db_ingestion_log": VectorDbIngestionLog,
    "api_keys": ApiKey,
}

# Tables that require account_id filtering for security
ACCOUNT_SCOPED_TABLES = {
    "chat_app_sessions",
    "chat_app_messages", 
    "usage_credits",
    "vector_db_ingestion_log",
    "api_keys",
}

# Sensitive columns to exclude from results
SENSITIVE_COLUMNS = {
    "hashed_password",
    "reset_token",
    "encrypted_api_key",
    "key_hash",
}


def serialize_value(value: Any) -> Any:
    """Serialize a database value to JSON-compatible format."""
    if value is None:
        return None
    elif hasattr(value, 'isoformat'):  # datetime objects
        return value.isoformat()
    elif hasattr(value, '__dict__'):  # Complex objects
        return str(value)
    else:
        return value


async def create_db_read_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Session,
    auth_token: Optional[str] = None,
    **kwargs
) -> Optional[StructuredTool]:
    """
    Create a database read tool for querying specific tables.
    
    Args:
        tool_config: Tool configuration with table name and filters
        account_id: Account ID for security filtering
        db: Database session
        auth_token: Authentication token (unused for DB queries)
        **kwargs: Additional context (unused)
        
    Returns:
        StructuredTool for database queries, or None if setup fails
        
    Example tool_config:
        {
            "type": "dbRead",
            "table": "chat_app_sessions",
            "description": "Query chat sessions",
            "columns": ["id", "session_id", "title", "created_at"],
            "limit": 50
        }
    """
    table_name = tool_config.get('table', '').lower()
    description = tool_config.get('description', f"Query data from {table_name} table")
    columns = tool_config.get('columns', [])  # Empty list means all columns
    default_limit = tool_config.get('limit', 50)
    
    # Validate required fields
    if not table_name:
        print(f"[DB READ TOOL] Missing required field: table")
        return None
    
    # Validate table is in whitelist
    if table_name not in ALLOWED_TABLES:
        print(f"[DB READ TOOL] Table '{table_name}' is not in allowed list. Allowed tables: {list(ALLOWED_TABLES.keys())}")
        return None
    
    model_class = ALLOWED_TABLES[table_name]
    is_account_scoped = table_name in ACCOUNT_SCOPED_TABLES
    
    print(f"[DB READ TOOL] Created tool for table: {table_name} (account_scoped={is_account_scoped})")
    
    # Define the query implementation
    async def query_impl(
        filters: Dict[str, Any] = None,
        limit: int = default_limit,
        offset: int = 0
    ) -> DbReadSuccess | DbReadError:
        """Query the database table with optional filters."""
        # DEBUG: Tool invocation
        print(f"\n{'='*60}")
        print(f"[DB READ TOOL] 🚀 TOOL INVOKED: query_{table_name}")
        print(f"[DB READ TOOL] 📊 Table: {table_name}")
        print(f"[DB READ TOOL] 🔍 Filters: {filters}")
        print(f"[DB READ TOOL] 📈 Limit: {limit}, Offset: {offset}")
        print(f"{'='*60}\n")
        
        try:
            # Start with base query
            query = db.query(model_class)
            
            # Apply account_id filter for scoped tables (SECURITY)
            if is_account_scoped:
                query = query.filter(model_class.account_id == account_id)
                print(f"[DB READ TOOL] 🔒 Applied account_id filter: {account_id}")
            
            # Apply custom filters if provided
            if filters:
                for column_name, value in filters.items():
                    if hasattr(model_class, column_name):
                        column = getattr(model_class, column_name)
                        query = query.filter(column == value)
                        print(f"[DB READ TOOL] 🔍 Applied filter: {column_name} = {value}")
                    else:
                        print(f"[DB READ TOOL] ⚠️  Ignoring invalid column: {column_name}")
            
            # Apply pagination
            query = query.limit(limit).offset(offset)
            
            # Execute query
            print(f"[DB READ TOOL] 📡 Executing query...")
            rows = query.all()
            
            print(f"[DB READ TOOL] ✅ Query complete: {len(rows)} rows returned")
            
            # Get column names from the model
            mapper = inspect(model_class)
            all_columns = [column.key for column in mapper.columns]
            
            # Filter columns if specified
            if columns:
                selected_columns = [col for col in columns if col in all_columns]
            else:
                selected_columns = all_columns
            
            # Remove sensitive columns
            selected_columns = [col for col in selected_columns if col not in SENSITIVE_COLUMNS]
            
            # Format results
            formatted_results = []
            for row in rows:
                row_data = {}
                for column_name in selected_columns:
                    if hasattr(row, column_name):
                        value = getattr(row, column_name)
                        row_data[column_name] = serialize_value(value)
                
                formatted_results.append({
                    "data": row_data
                })
            
            print(f"[DB READ TOOL] 🎯 Returning {len(formatted_results)} results")
            print(f"{'='*60}\n")
            
            return {
                "results": formatted_results,
                "table": table_name,
                "count": len(formatted_results)
            }
        except Exception as e:
            print(f"\n[DB READ TOOL] ❌❌❌ EXCEPTION CAUGHT ❌❌❌")
            print(f"[DB READ TOOL] Error: {e}")
            print(f"[DB READ TOOL] Type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            return {"error": str(e)}
    
    # Define the Pydantic schema for the tool arguments
    class QueryInput(BaseModel):
        filters: Optional[Dict[str, Any]] = Field(
            default=None,
            description="Optional filters to apply (e.g., {'status': 'active'})"
        )
        limit: int = Field(
            default=default_limit,
            description=f"Maximum number of results to return (default: {default_limit})",
            ge=1,
            le=100
        )
        offset: int = Field(
            default=0,
            description="Number of results to skip (for pagination)",
            ge=0
        )
    
    # Create and return the StructuredTool
    tool_name = f"query_{table_name}"
    
    return StructuredTool(
        func=query_impl,
        coroutine=query_impl,
        name=tool_name,
        description=description,
        args_schema=QueryInput
    )
