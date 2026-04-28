"""
Delete prompt endpoint.

Also removes the corresponding vector from the ``prompts`` namespace in
Pinecone so search results stay in sync.
"""
import logging
import os
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from src.core.clients import pc
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

PINECONE_INDEX = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
PROMPTS_NAMESPACE = "prompts"

router = APIRouter()

@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
async def delete_prompt(
    prompt_id: int,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Delete a prompt and its corresponding Pinecone vector.
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
        
        db.delete(prompt)
        db.commit()

        # ── Remove vector from Pinecone ──────────────────────────────
        try:
            if PINECONE_INDEX:
                index = pc.Index(PINECONE_INDEX)
                index.delete(ids=[f"prompt_{prompt_id}"], namespace=PROMPTS_NAMESPACE)
                logger.info("[DELETE PROMPT] Removed vector prompt_%s from Pinecone", prompt_id)
        except Exception as vec_err:
            logger.warning("[DELETE PROMPT] Failed to delete vector: %s", vec_err)
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[DELETE PROMPT]")
