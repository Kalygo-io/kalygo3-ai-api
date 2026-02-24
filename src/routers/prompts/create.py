"""
Create prompt endpoint.

After persisting the prompt to the DB, embeds its content and upserts the
vector into the ``prompts`` namespace in Pinecone so it is searchable via
similarity search.
"""
import os
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from src.services import fetch_embedding
from src.core.clients import pc
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import CreatePromptRequest, PromptResponse

PINECONE_INDEX = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
PROMPTS_NAMESPACE = "prompts"

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


def _extract_token(request: Request) -> str | None:
    token = request.cookies.get("jwt")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
    return token


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

    The prompt is saved to the database and then embedded + upserted into
    Pinecone (``prompts`` namespace) for similarity search.
    """
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )
        
        if not request_body.name or not request_body.name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt name cannot be empty"
            )
        
        if not request_body.content or not request_body.content.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prompt content cannot be empty"
            )
        
        prompt = Prompt(
            account_id=account_id,
            name=request_body.name.strip(),
            description=request_body.description.strip() if request_body.description else None,
            content=request_body.content
        )
        
        db.add(prompt)
        db.commit()
        db.refresh(prompt)

        # ── Embed + upsert to Pinecone ───────────────────────────────
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
                print(f"[CREATE PROMPT] Embedded prompt {prompt.id} into Pinecone")
        except Exception as embed_err:
            # Don't fail the create if embedding fails
            print(f"[CREATE PROMPT] Warning: embedding failed: {embed_err}")
        
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
