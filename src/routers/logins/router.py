from pydantic import BaseModel
from typing import Optional
from fastapi import APIRouter, Request, status

from src.db.models import Logins
from src.deps import db_dependency, jwt_dependency

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.get('/')
@limiter.limit("100/minute")
def get_logins(db: db_dependency, jwt: jwt_dependency, request: Request, cursor: Optional[int]):

    print('cursor', cursor)

    results = db.query(Logins).filter(Logins.account_id == jwt.get('id')).order_by(Logins.created_at.desc()).offset(cursor).limit(40).all()

    results = [{
        "id": r.id,
        'account_id': r.account_id,
        'ip_address': r.ip_address,
        'created_at': r.created_at,
        'similarity_score': r.similarity_score
    } for r in results]

    return {
        "results": results,
        "cursor": cursor + 40
    }
