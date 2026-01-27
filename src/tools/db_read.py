"""
Database Read Tool

Provides read access to external database tables via stored credentials.
Allows agents to query structured data from user-configured databases.
"""
from typing import Dict, Any, Optional, List, TypedDict
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine
from src.db.models import Credential
from src.routers.credentials.encryption import decrypt_credential_data


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


def serialize_value(value: Any) -> Any:
    """Serialize a database value to JSON-compatible format."""
    if value is None:
        return None
    elif hasattr(value, 'isoformat'):  # datetime objects
        return value.isoformat()
    elif isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    elif hasattr(value, '__dict__'):  # Complex objects
        return str(value)
    else:
        return value


class CredentialError(Exception):
    """Raised when there's an issue with a credential required by a tool."""
    pass


def get_connection_string(credential_id: int, account_id: int, db: Session) -> str:
    """
    Retrieve and decrypt the connection string from a stored credential.
    
    Args:
        credential_id: ID of the credential to look up
        account_id: Account ID for security (must own the credential)
        db: Database session
        
    Returns:
        Decrypted connection string
        
    Raises:
        CredentialError: If credential not found, unauthorized, wrong type, or decryption fails
    """
    # Look up the credential (must belong to the account)
    credential = db.query(Credential).filter(
        Credential.id == credential_id,
        Credential.account_id == account_id
    ).first()
    
    if not credential:
        raise CredentialError(
            f"Credential with ID {credential_id} not found. "
            f"It may have been deleted or you don't have access to it."
        )
    
    if credential.credential_type != "db_connection":
        raise CredentialError(
            f"Credential {credential_id} is not a database connection. "
            f"Expected type 'db_connection', got '{credential.credential_type}'."
        )
    
    try:
        # Decrypt the credential data
        credential_data = decrypt_credential_data(credential.encrypted_data)
        
        # Get the connection string
        connection_string = credential_data.get("connection_string")
        if not connection_string:
            raise CredentialError(
                f"Credential {credential_id} does not contain a 'connection_string'. "
                f"Available keys: {list(credential_data.keys())}"
            )
        
        return connection_string
    except CredentialError:
        raise
    except Exception as e:
        raise CredentialError(f"Failed to decrypt credential {credential_id}: {e}")


async def create_db_read_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Session,
    auth_token: Optional[str] = None,
    **kwargs
) -> StructuredTool:
    """
    Create a database read tool for querying external database tables.
    
    Args:
        tool_config: Tool configuration including:
            - credentialId: ID of stored credential with connection string
            - table: Table name to query
            - name: Optional custom tool name
            - description: Description for the LLM
            - columns: List of columns to expose (required for security)
            - maxLimit: Maximum rows per query
        account_id: Account ID for credential lookup
        db: Database session (for credential lookup)
        auth_token: Authentication token (unused)
        **kwargs: Additional context (unused)
        
    Returns:
        StructuredTool for database queries, or None if setup fails
        
    Example tool_config:
        {
            "type": "dbRead",
            "credentialId": 6,
            "table": "users",
            "name": "query_users",
            "description": "Query user records from the users table",
            "columns": ["id", "name", "email", "created_at"],
            "maxLimit": 100
        }
    """
    credential_id = tool_config.get('credentialId')
    table_name = tool_config.get('table', '').strip()
    tool_name = tool_config.get('name', f"query_{table_name}").strip()
    description = tool_config.get('description', f"Query data from {table_name} table")
    allowed_columns = tool_config.get('columns', [])
    max_limit = tool_config.get('maxLimit', 100)
    
    # Validate required fields
    if not credential_id:
        raise CredentialError("Missing required field 'credentialId' in dbRead tool configuration")
    
    if not table_name:
        raise ValueError("Missing required field 'table' in dbRead tool configuration")
    
    # Get the connection string from the credential (raises CredentialError if fails)
    connection_string = get_connection_string(credential_id, account_id, db)
    
    # Create the database engine for the external database
    try:
        external_engine = create_engine(connection_string, pool_pre_ping=True)
        print(f"[DB READ TOOL] Created connection to external database for table: {table_name}")
    except Exception as e:
        raise CredentialError(
            f"Failed to connect to database using credential {credential_id}: {e}"
        )
    
    # Validate the table exists and get its columns
    try:
        with external_engine.connect() as conn:
            inspector = inspect(external_engine)
            tables = inspector.get_table_names()
            
            if table_name not in tables:
                available = tables[:10]
                raise ValueError(
                    f"Table '{table_name}' not found in database. "
                    f"Available tables: {available}{'...' if len(tables) > 10 else ''}"
                )
            
            # Get actual column names from the table
            table_columns = [col['name'] for col in inspector.get_columns(table_name)]
            print(f"[DB READ TOOL] Table '{table_name}' columns: {table_columns}")
            
            # Validate allowed_columns exist in the table
            if allowed_columns:
                invalid_columns = [col for col in allowed_columns if col not in table_columns]
                if invalid_columns:
                    raise ValueError(
                        f"Invalid columns specified: {invalid_columns}. "
                        f"Available columns in '{table_name}': {table_columns}"
                    )
                selected_columns = allowed_columns
            else:
                # If no columns specified, use all columns (not recommended for security)
                print(f"[DB READ TOOL] ⚠️ Warning: No columns specified, exposing all columns")
                selected_columns = table_columns
                
    except (CredentialError, ValueError):
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate table '{table_name}': {e}")
    
    print(f"[DB READ TOOL] Tool '{tool_name}' ready for table: {table_name} (columns: {selected_columns})")
    
    # Define the query implementation
    async def query_impl(
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> DbReadSuccess | DbReadError:
        """Query the external database table with optional filters."""
        # DEBUG: Tool invocation
        print(f"\n{'='*60}")
        print(f"[DB READ TOOL] 🚀 TOOL INVOKED: {tool_name}")
        print(f"[DB READ TOOL] 📊 Table: {table_name}")
        print(f"[DB READ TOOL] 🔍 Filters: {filters}")
        print(f"[DB READ TOOL] 📈 Limit: {limit}, Offset: {offset}")
        print(f"{'='*60}\n")
        
        try:
            # Enforce max limit
            if limit > max_limit:
                limit = max_limit
                print(f"[DB READ TOOL] ⚠️ Limit capped to max: {max_limit}")
            
            # Build the SELECT query with only allowed columns
            columns_sql = ", ".join([f'"{col}"' for col in selected_columns])
            query_sql = f'SELECT {columns_sql} FROM "{table_name}"'
            
            # Add WHERE clause for filters
            params = {}
            if filters:
                where_clauses = []
                for i, (column_name, value) in enumerate(filters.items()):
                    # Only allow filtering on allowed columns
                    if column_name in selected_columns:
                        param_name = f"p{i}"
                        where_clauses.append(f'"{column_name}" = :{param_name}')
                        params[param_name] = value
                        print(f"[DB READ TOOL] 🔍 Applied filter: {column_name} = {value}")
                    else:
                        print(f"[DB READ TOOL] ⚠️ Ignoring filter on non-allowed column: {column_name}")
                
                if where_clauses:
                    query_sql += " WHERE " + " AND ".join(where_clauses)
            
            # Add LIMIT and OFFSET
            query_sql += f" LIMIT :limit OFFSET :offset"
            params["limit"] = limit
            params["offset"] = offset
            
            print(f"[DB READ TOOL] 📡 Executing query: {query_sql}")
            
            # Execute query
            with external_engine.connect() as conn:
                result = conn.execute(text(query_sql), params)
                rows = result.fetchall()
                column_names = result.keys()
            
            print(f"[DB READ TOOL] ✅ Query complete: {len(rows)} rows returned")
            
            # Format results
            formatted_results = []
            for row in rows:
                row_data = {}
                for col_name, value in zip(column_names, row):
                    row_data[col_name] = serialize_value(value)
                formatted_results.append({"data": row_data})
            
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
            description=f"Optional filters to apply. Allowed columns: {selected_columns}"
        )
        limit: int = Field(
            default=50,
            description=f"Maximum number of results to return (max: {max_limit})",
            ge=1,
            le=max_limit
        )
        offset: int = Field(
            default=0,
            description="Number of results to skip (for pagination)",
            ge=0
        )
    
    # Create and return the StructuredTool
    return StructuredTool(
        func=query_impl,
        coroutine=query_impl,
        name=tool_name,
        description=description,
        args_schema=QueryInput
    )
