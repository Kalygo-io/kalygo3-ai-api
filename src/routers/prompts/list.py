"""
List prompts endpoint.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import PromptResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/", response_model=List[PromptResponse])
@limiter.limit("60/minute")
async def list_prompts(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    List all prompts for the authenticated user.
    
    Returns prompts ordered by most recently updated first.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        prompts = db.query(Prompt).filter(
            Prompt.account_id == account_id
        ).order_by(Prompt.updated_at.desc()).all()
        
        return prompts
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[LIST PROMPTS] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list prompts: {str(e)}"
        )
