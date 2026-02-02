"""
Update prompt endpoint.
"""
from fastapi import APIRouter, HTTPException, status, Request
from src.deps import db_dependency, jwt_dependency
from src.db.models import Prompt, Account
from slowapi import Limiter
from slowapi.util import get_remote_address

from .models import UpdatePromptRequest, PromptResponse

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


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
    
    Only updates prompts that belong to the authenticated user.
    All fields are optional - only provided fields will be updated.
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
        
        # Update fields if provided
        if request_body.name is not None:
            if not request_body.name.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prompt name cannot be empty"
                )
            prompt.name = request_body.name.strip()
        
        if request_body.description is not None:
            prompt.description = request_body.description.strip() if request_body.description else None
        
        if request_body.content is not None:
            if not request_body.content.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Prompt content cannot be empty"
                )
            prompt.content = request_body.content
        
        db.commit()
        db.refresh(prompt)
        
        return prompt
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"[UPDATE PROMPT] Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update prompt: {str(e)}"
        )
