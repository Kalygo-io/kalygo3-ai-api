from fastapi import APIRouter, Request, Response

from slowapi.util import get_remote_address
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.get("/")
@limiter.limit("5/minute")  # 5 requests per minute
def healthcheck(request: Request, response: Response):
    print("healthcheck")
    return {"status": "OK!"}