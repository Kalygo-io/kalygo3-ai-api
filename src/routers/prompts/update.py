"""
Update prompt endpoint.

After updating the DB row, re-embeds the content and upserts the vector
into the ``prompts`` namespace in Pinecone so search results stay fresh.
"""
import logging
import os
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from src.services import fetch_embedding
from src.core.clients import pc

from .models import UpdatePromptRequest, PromptResponse
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

PINECONE_INDEX = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
PROMPTS_NAMESPACE = "prompts"

router = APIRouter()

def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("jwt")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
    return token

@router.put("/{prompt_id}", response_model=PromptResponse)
@limiter.limit("30/minute")
async def update_prompt(
    prompt_id: int,
    request_body: UpdatePromptRequest,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Update an existing prompt.

    If content, name, or description changed the vector in Pinecone is
    re-embedded and upserted so search stays in sync.
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
        
        needs_reembed = False

        if request_body.name is not None:
            if not request_body.name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prompt name cannot be empty"
                )
            prompt.name = request_body.name.strip()
            needs_reembed = True
        
        if request_body.description is not None:
            prompt.description = request_body.description.strip() if request_body.description else None
            needs_reembed = True
        
        if request_body.content is not None:
            if not request_body.content.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prompt content cannot be empty"
                )
            prompt.content = request_body.content
            needs_reembed = True
        
        db.commit()
        db.refresh(prompt)

        # ── Re-embed + upsert to Pinecone ────────────────────────────
        if needs_reembed:
            try:
                token = _extract_token(request)
                embedding = await fetch_embedding(token, prompt.content)

                if embedding and PINECONE_INDEX:
                    index = pc.Index(PINECONE_INDEX)
                    index.upsert(
                        vectors=[(
                            f"prompt_{prompt.id}",
                            embedding,
                            {
                                "prompt_id": prompt.id,
                                "account_id": account_id,
                                "name": prompt.name,
                                "description": prompt.description or "",
                                "content": prompt.content,
                                "type": "prompt",
                            },
                        )],
                        namespace=PROMPTS_NAMESPACE,
                    )
                    logger.info("[UPDATE PROMPT] Re-embedded prompt %s into Pinecone", prompt.id)
            except Exception as embed_err:
                logger.warning("[UPDATE PROMPT] Re-embedding failed: %s", embed_err)
        
        return prompt
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[UPDATE PROMPT]")
