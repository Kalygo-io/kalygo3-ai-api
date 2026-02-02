"""
Get prompt endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import PromptResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/{prompt_id}", response_model=PromptResponse)
@limiter.limit("60/minute")
async def get_prompt(
    prompt_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Get a specific prompt by ID.
    
    Only returns prompts that belong to the authenticated user.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        prompt = db.query(Prompt).filter(
            Prompt.id == prompt_id,
            Prompt.account_id == account_id
        ).first()
        
        if not prompt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prompt not found"
            )
        
        return prompt
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[GET PROMPT] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get prompt: {str(e)}"
        )
