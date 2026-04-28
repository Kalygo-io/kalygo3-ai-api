from fastapi import APIRouter, Response, status, Request
from pydantic import BaseModel
from src.db.waitlist import Waitlist
from src.deps import db_dependency
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

router = APIRouter()

class JoinWaitlistRequestBody(BaseModel):
    email: str

@router.post("/join")
async def create_account(db: db_dependency, body: JoinWaitlistRequestBody, request: Request):
    try:
        create_account_model = Waitlist(
            email=body.email,
            
        )
        db.add(create_account_model)
        db.commit()
        db.refresh(create_account_model)

        return Response(status_code=status.HTTP_201_CREATED)
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[JOIN WAITLIST]")