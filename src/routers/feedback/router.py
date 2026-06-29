from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Request, Response, status
from pydantic import BaseModel, Field

from src.db.feedback import Feedback
from src.deps import db_dependency
from src.rate_limit import limiter
from src.utils.errors import handle_db_error

from .admin_notification import send_feedback_notification_to_admin

router = APIRouter()

FeedbackCategory = Literal["bug", "feature", "question", "other"]


class SubmitFeedbackRequestBody(BaseModel):
    # Which branded UI this came from, e.g. "bolay". Lets one table serve many UIs.
    client: str = Field(min_length=1, max_length=64)
    category: FeedbackCategory
    message: str = Field(min_length=1, max_length=10_000)
    # Optional contact email so an admin can follow up. Empty string → None.
    email: Optional[str] = Field(default=None, max_length=320)


@router.post("/")
@limiter.limit("10/minute")
async def submit_feedback(
    db: db_dependency,
    body: SubmitFeedbackRequestBody,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Public endpoint: record feedback and email the admin.

    No auth — the feedback form is reachable while logged out. `client`
    differentiates submissions from multiple branded front-ends.
    """
    email = body.email.strip() if body.email and body.email.strip() else None
    try:
        feedback = Feedback(
            client=body.client,
            category=body.category,
            email=email,
            message=body.message,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[SUBMIT FEEDBACK]")

    # Notify the admin out-of-band so a slow/failed email never blocks the user.
    background_tasks.add_task(
        send_feedback_notification_to_admin,
        client=body.client,
        category=body.category,
        email=email,
        message=body.message,
    )

    return Response(status_code=status.HTTP_201_CREATED)
