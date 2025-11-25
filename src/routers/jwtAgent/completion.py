from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt
from src.deps import db_dependency, jwt_dependency  # db unused but kept for compatibility

import httpx
import os
import json
from typing import Optional

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# Point this to your n8n webhook (test or production)
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    # "https://commandlabs.app.n8n.cloud/webhook-test/2202b519-db70-489a-841a-b1df7e661ca9",
    "https://commandlabs.app.n8n.cloud/webhook/2202b519-db70-489a-841a-b1df7e661ca9"
)

async def n8n_completion_stream(
    session_id: str,
    user_prompt: str,
    jwt_claims: dict,
    raw_jwt: Optional[str],
):
    """
    Call the n8n webhook and stream its response back as a single 'completion' event.
    We relay the incoming JWT cookie to n8n.
    """
    headers = {"Content-Type": "application/json"}

    # Relay JWT from cookie as an Authorization header for n8n
    if raw_jwt:
        headers["Authorization"] = f"Bearer {raw_jwt}"

    # Adjust this payload to whatever your n8n workflow expects
    payload = {
        "sessionId": session_id,
        "prompt": user_prompt,
        "jwt": jwt_claims,  # decoded token from jwt_dependency
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            # Stream an error event instead of throwing mid-stream
            error_event = {
                "event": "error",
                "message": str(exc),
            }
            yield json.dumps(error_event, separators=(",", ":"))
            return

        # Try JSON first, fall back to plain text
        try:
            n8n_data = resp.json()
        except ValueError:
            n8n_data = resp.text

        event = {
            "event": "completion",
            "data": n8n_data,
        }

        yield json.dumps(event, separators=(",", ":"))


@router.post("/completion")
@limiter.limit("10/minute")
def prompt(
    prompt: ChatSessionPrompt,
    jwt: jwt_dependency,
    db: db_dependency,  # kept for signature compatibility; not used here
    request: Request,
):
    # Same pattern you mentioned:
    raw_jwt = request.cookies.get("jwt") if request else None

    return StreamingResponse(
        n8n_completion_stream(prompt.sessionId, prompt.prompt, jwt, raw_jwt),
        media_type="text/event-stream",
    )
