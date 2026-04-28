import logging
from typing import Optional
from fastapi import APIRouter, Request

from src.db.models import Logins
from src.deps import db_dependency, jwt_dependency
from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get('/')
@limiter.limit("100/minute")
def get_logins(db: db_dependency, jwt: jwt_dependency, request: Request, cursor: Optional[int] = 0):
    try:
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
    except Exception as e:
        raise handle_db_error(e, "[GET LOGINS]")
