"""
Create prompt endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import CreatePromptRequest, PromptResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=PromptResponse)
@limiter.limit("30/minute")
async def create_prompt(
    request_body: CreatePromptRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Create a new prompt.
    
    The prompt will be associated with the authenticated user's account.
    
    Required fields:
    - name: A descriptive name for the prompt
    - content: The actual prompt text/template
    
    Optional fields:
    - description: Additional context about what the prompt does
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        # Validate name is not empty
        if not request_body.name or not request_body.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt name cannot be empty"
            )
        
        # Validate content is not empty
        if not request_body.content or not request_body.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt content cannot be empty"
            )
        
        # Create prompt
        prompt = Prompt(
            account_id=account_id,
            name=request_body.name.strip(),
            description=request_body.description.strip() if request_body.description else None,
            content=request_body.content
        )
        
        db.add(prompt)
        db.commit()
        db.refresh(prompt)
        
        return prompt
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[CREATE PROMPT] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create prompt: {str(e)}"
        )
