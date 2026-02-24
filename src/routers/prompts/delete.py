"""
Delete prompt endpoint.

Also removes the corresponding vector from the ``prompts`` namespace in
Pinecone so search results stay in sync.
"""
import os
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from src.core.clients import pc
from slowapi import Limiter
from slowapi.util import get_remote_address

PINECONE_INDEX = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
PROMPTS_NAMESPACE = "prompts"

limiter = Limiter(key_func=get_remote_address)
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
                print(f"[DELETE PROMPT] Removed vector prompt_{prompt_id} from Pinecone")
        except Exception as vec_err:
            print(f"[DELETE PROMPT] Warning: failed to delete vector: {vec_err}")
        
        return None
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[DELETE PROMPT] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete prompt: {str(e)}"
        )
