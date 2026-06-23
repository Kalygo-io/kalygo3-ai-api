"""
List prompts endpoint.
"""
from typing import List
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency, account_id_from_claims, ensure_account
from src.db.models import Prompt

from .models import PromptResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

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
        account_id = account_id_from_claims(jwt)
        account = ensure_account(db, account_id)
        
        prompts = db.query(Prompt).filter(
            Prompt.account_id == account_id
        ).order_by(Prompt.updated_at.desc()).all()
        
        return prompts
        
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[LIST PROMPTS]")
