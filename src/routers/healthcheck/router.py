from fastapi import APIRouter, Request, Response

router = APIRouter()

@router.get("/")
def health_check(request: Request, response: Response):
    """
    Health check endpoint for Cloud Run.
    No rate limiting to ensure health checks always succeed.
    """
    # response.status_code = 200
    return {"status": "OK!"}