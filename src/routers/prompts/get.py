"""
Get prompt endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Prompt

from .models import PromptResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
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
        raise handle_db_error(e, "[GET PROMPT]")
