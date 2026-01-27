"""
Database Write Tool

Provides write access to external database tables via stored credentials.
Allows agents to insert records into user-configured databases.
"""
from typing import Dict, Any, Optional, List, TypedDict
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model
from sqlalchemy.orm import Session
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.pool import NullPool
from src.db.models import Credential
from src.routers.credentials.encryption import decrypt_credential_data

# Import shared utilities from db_read
from .db_read import CredentialError, get_connection_string, serialize_value


# Type definitions for database write results
class DbWriteSuccess(TypedDict):
    """Successful database write result."""
    success: bool
    table: str
    inserted: Dict[str, Any]
    message: str


class DbWriteError(TypedDict):
    """Error result from database write."""
    error: str


async def create_db_write_tool(
    tool_config: Dict[str, Any],
    account_id: int,
    db: Session,
    auth_token: Optional[str] = None,
    **kwargs
) -> StructuredTool:
    """
    Create a database write tool for inserting records into external database tables.
    
    Args:
        tool_config: Tool configuration including:
            - credentialId: ID of stored credential with connection string
            - table: Table name to write to
            - name: Optional custom tool name
            - description: Description for the LLM
            - columns: List of columns that can be written (required for security)
            - requiredColumns: List of columns that must be provided
            - injectAccountId: If true, automatically inject the account_id column
        account_id: Account ID for credential lookup and auto-injection
        db: Database session (for credential lookup)
        auth_token: Authentication token (unused)
        **kwargs: Additional context (unused)
        
    Returns:
        StructuredTool for database inserts
        
    Raises:
        CredentialError: If credential is invalid or missing
        ValueError: If configuration is invalid
        
    Example tool_config:
        {
            "type": "dbWrite",
            "credentialId": 6,
            "table": "leads",
            "name": "create_lead",
            "description": "Create a new lead record with contact information",
            "columns": ["name", "email", "phone", "description"],
            "requiredColumns": ["name"],
            "injectAccountId": true
        }
    """
    credential_id = tool_config.get('credentialId')
    table_name = tool_config.get('table', '').strip()
    tool_name = tool_config.get('name', f"insert_{table_name}").strip()
    description = tool_config.get('description', f"Insert a record into {table_name} table")
    allowed_columns = tool_config.get('columns', [])
    required_columns = tool_config.get('requiredColumns', [])
    inject_account_id = tool_config.get('injectAccountId', False)
    
    # Validate required fields
    if not credential_id:
        raise CredentialError("Missing required field 'credentialId' in dbWrite tool configuration")
    
    if not table_name:
        raise ValueError("Missing required field 'table' in dbWrite tool configuration")
    
    if not allowed_columns:
        raise ValueError("Missing required field 'columns' in dbWrite tool configuration. "
                        "You must specify which columns can be written for security.")
    
    # Validate requiredColumns are in allowed_columns
    invalid_required = [col for col in required_columns if col not in allowed_columns]
    if invalid_required:
        raise ValueError(f"requiredColumns contains columns not in allowed columns: {invalid_required}")
    
    # Get the connection string from the credential (raises CredentialError if fails)
    connection_string = get_connection_string(credential_id, account_id, db)
    
    # Create the database engine for the external database
    # Use NullPool to avoid creating persistent connection pools for each tool
    # Connections are created/closed on each query - better for tools that run infrequently
    try:
        external_engine = create_engine(
            connection_string, 
            poolclass=NullPool,  # No persistent pool - connections close after each use
            pool_pre_ping=True
        )
        print(f"[DB WRITE TOOL] Created connection to external database for table: {table_name}")
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
            print(f"[DB WRITE TOOL] Table '{table_name}' columns: {table_columns}")
            
            # Validate allowed_columns exist in the table
            invalid_columns = [col for col in allowed_columns if col not in table_columns]
            if invalid_columns:
                raise ValueError(
                    f"Invalid columns specified: {invalid_columns}. "
                    f"Available columns in '{table_name}': {table_columns}"
                )
                
    except (CredentialError, ValueError):
        raise
    except Exception as e:
        raise ValueError(f"Failed to validate table '{table_name}': {e}")
    
    print(f"[DB WRITE TOOL] Tool '{tool_name}' ready for table: {table_name}")
    print(f"[DB WRITE TOOL] Allowed columns: {allowed_columns}")
    print(f"[DB WRITE TOOL] Required columns: {required_columns}")
    print(f"[DB WRITE TOOL] Inject account_id: {inject_account_id}")
    
    # Define the insert implementation that accepts **kwargs for flat schema
    async def insert_impl(**kwargs) -> DbWriteSuccess | DbWriteError:
        """Insert a record into the external database table."""
        # DEBUG: Tool invocation
        print(f"\n{'='*60}")
        print(f"[DB WRITE TOOL] 🚀 TOOL INVOKED: {tool_name}")
        print(f"[DB WRITE TOOL] 📊 Table: {table_name}")
        print(f"[DB WRITE TOOL] 📝 Input kwargs: {kwargs}")
        print(f"{'='*60}\n")
        
        try:
            # Validate required columns are present
            missing_required = [col for col in required_columns if col not in kwargs or kwargs[col] is None]
            if missing_required:
                return {"error": f"Missing required columns: {missing_required}"}
            
            # Filter data to only allowed columns (should already be filtered by schema, but double-check)
            filtered_data = {}
            for col in allowed_columns:
                if col in kwargs and kwargs[col] is not None:
                    filtered_data[col] = kwargs[col]
            
            # Auto-inject account_id if configured
            # This ensures the record is associated with the authenticated user's account
            if inject_account_id:
                filtered_data['account_id'] = account_id
                print(f"[DB WRITE TOOL] 🔐 Auto-injected account_id: {account_id}")
            
            if not filtered_data:
                return {"error": "No valid columns provided. "
                               f"Allowed columns: {allowed_columns}"}
            
            # Build the INSERT query
            columns = list(filtered_data.keys())
            columns_sql = ", ".join([f'"{col}"' for col in columns])
            placeholders = ", ".join([f":{col}" for col in columns])
            
            query_sql = f'INSERT INTO "{table_name}" ({columns_sql}) VALUES ({placeholders}) RETURNING *'
            
            print(f"[DB WRITE TOOL] 📡 Executing query: {query_sql}")
            print(f"[DB WRITE TOOL] 📝 Parameters: {filtered_data}")
            
            # Execute insert
            with external_engine.connect() as conn:
                result = conn.execute(text(query_sql), filtered_data)
                inserted_row = result.fetchone()
                column_names = result.keys()
                conn.commit()
            
            # Format the inserted row
            inserted_data = {}
            if inserted_row:
                for col_name, value in zip(column_names, inserted_row):
                    # Only return allowed columns in the response
                    if col_name in allowed_columns or col_name == 'id':
                        inserted_data[col_name] = serialize_value(value)
            
            print(f"[DB WRITE TOOL] ✅ Insert complete")
            print(f"[DB WRITE TOOL] 🎯 Inserted: {inserted_data}")
            print(f"{'='*60}\n")
            
            return {
                "success": True,
                "table": table_name,
                "inserted": inserted_data,
                "message": f"Successfully inserted record into {table_name}"
            }
            
        except Exception as e:
            print(f"\n[DB WRITE TOOL] ❌❌❌ EXCEPTION CAUGHT ❌❌❌")
            print(f"[DB WRITE TOOL] Error: {e}")
            print(f"[DB WRITE TOOL] Type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            print(f"{'='*60}\n")
            return {"error": str(e)}
    
    # Dynamically create a Pydantic model with each column as a direct field
    # This creates a flat schema that LLMs understand better than nested Dict fields
    field_definitions = {}
    for col in allowed_columns:
        # Required columns are not Optional, optional columns are Optional with None default
        if col in required_columns:
            field_definitions[col] = (
                str,  # Type - using str as it's most common, values get converted by DB
                Field(..., description=f"Value for column '{col}' (required)")
            )
        else:
            field_definitions[col] = (
                Optional[str],  # Optional type
                Field(default=None, description=f"Value for column '{col}' (optional)")
            )
    
    # Create the dynamic Pydantic model
    InsertInput = create_model(
        f"InsertInput_{table_name}",
        **field_definitions
    )
    
    # Update the model's docstring for better LLM understanding
    required_str = f" Required fields: {required_columns}." if required_columns else ""
    InsertInput.__doc__ = f"Input schema for inserting a record into {table_name}.{required_str}"
    
    print(f"[DB WRITE TOOL] Created dynamic schema with fields: {list(field_definitions.keys())}")
    
    # Create and return the StructuredTool
    return StructuredTool(
        func=insert_impl,
        coroutine=insert_impl,
        name=tool_name,
        description=description,
        args_schema=InsertInput
    )
