from fastapi import APIRouter, HTTPException, Request, status
import uuid

from src.db.models import ChatMessage, ChatSession
from src.deps import db_dependency, jwt_dependency

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.delete("/chat-sessions/{session_id}/messages", status_code=status.HTTP_200_OK)
@limiter.limit("10/minute")
async def delete_session_messages(
    session_id: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """
    Delete all messages for a specific session.
    Verifies that the session belongs to the authenticated user before deletion.
    """
    try:
        print(f"DELETE /sessions/{session_id}/messages - JWT: {jwt}")
        
        # Convert string to UUID for database query
        session_uuid = uuid.UUID(session_id)
        
        # Convert jwt['id'] to int for database comparison
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        
        # Verify the session exists and belongs to the user
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.account_id == account_id
        ).first()
        
        if not session:
            print(f"Session {session_uuid} not found for account_id {account_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Session not found",
                    "message": "The specified session was not found or does not belong to you.",
                    "hint": "Please check the sessionId or ensure you have access to this session."
                }
            )
        
        # Get all messages for this session
        messages = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id
        ).all()
        
        print(f"Found {len(messages)} messages to delete for session {session_uuid}")
        
        # Delete all messages
        deleted_count = len(messages)
        for message in messages:
            db.delete(message)
        
        db.commit()
        
        print(f"Successfully deleted {deleted_count} messages from session {session_uuid}")
        
        return {
            "success": True,
            "message": f"Successfully deleted {deleted_count} message(s) from session",
            "session_id": str(session_uuid),
            "deleted_count": deleted_count
        }
        
    except ValueError as e:
        print(f"ValueError in delete_session_messages: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Invalid sessionId format",
                "message": "The sessionId must be a valid UUID format.",
                "hint": "Please provide a valid UUID for the sessionId."
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Exception in delete_session_messages: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to delete messages",
                "message": "An error occurred while deleting messages.",
                "hint": str(e)
            }
        )

