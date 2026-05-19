import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status, Request
from pydantic import BaseModel
from src.deps import db_dependency, jwt_dependency
from src.db.models import ChatSession, ChatMessage, Contact
from src.services.agent_access import can_access_agent
import uuid
from datetime import datetime

from src.utils.errors import handle_db_error
from src.rate_limit import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

# Pydantic models for request/response
class ChatSessionCreate(BaseModel):
    # agentId is optional: contact-scoped sessions have no DB agent (the
    # contact-chat endpoint injects a code-defined config instead).
    agentId: Optional[int] = None
    title: Optional[str] = None
    contactId: Optional[int] = None

class ChatSessionUpdate(BaseModel):
    title: Optional[str] = None

def to_camel(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])

class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    createdAt: datetime
    toolCalls: Optional[List[dict]] = None

class ChatSessionResponse(BaseModel):
    id: int
    sessionId: uuid.UUID
    agentId: Optional[int] = None
    accountId: int
    createdAt: datetime
    title: Optional[str] = None
    contactId: Optional[int] = None

class ChatSessionWithMessagesResponse(BaseModel):
    id: int
    sessionId: uuid.UUID
    agentId: Optional[int] = None
    accountId: int
    createdAt: datetime
    title: Optional[str] = None
    contactId: Optional[int] = None
    messages: List[ChatMessageResponse] = []

    class Config:
        from_attributes = True
        alias_generator = to_camel

class ChatMessageCreateRequest(BaseModel):
    message: dict

class ChatMessageDetailResponse(BaseModel):
    id: int
    message: dict
    session_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# CRUD Operations for ChatSession

@router.post("/sessions", response_model=ChatSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_session(
    sessionData: ChatSessionCreate, 
    db: db_dependency, 
    jwt: jwt_dependency, 
    request: Request
):
    """Create a new chat session"""
    try:
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']

        # Verify the caller can access the requested agent
        if sessionData.agentId and not can_access_agent(db, account_id, sessionData.agentId):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this agent"
            )

        # Contact ownership gate: a session may only be bound to a contact the
        # caller's account owns. This is the layer-2 control that makes the
        # contact binding a trustworthy scope (404, not 403, to avoid leaking
        # the existence of other accounts' contact ids).
        if sessionData.contactId is not None:
            owned_contact = db.query(Contact).filter(
                Contact.id == sessionData.contactId,
                Contact.account_id == account_id,
            ).first()
            if not owned_contact:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Contact not found"
                )

        # Generate a new UUID for the session
        session_uuid = str(uuid.uuid4())

        # Create the session
        new_session = ChatSession(
            session_id=session_uuid,
            agent_id=sessionData.agentId,
            account_id=jwt['id'],
            title=sessionData.title,
            contact_id=sessionData.contactId
        )

        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        return {
            "id": new_session.id,
            "sessionId": new_session.session_id,
            "agentId": new_session.agent_id,
            "accountId": new_session.account_id,
            "createdAt": new_session.created_at,
            "title": new_session.title,
            "contactId": new_session.contact_id
        }
    except HTTPException:
        # Intentional 4xx (agent-access 403, contact-ownership 404) must not be
        # remapped to 500 by the generic DB error handler.
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[OPERATION]")

@router.get("/sessions", response_model=List[ChatSessionResponse])
@limiter.limit("30/minute")
async def get_sessions(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    agent_id: Optional[int] = None,
    contact_id: Optional[int] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get sessions for the authenticated user.

    Contact-bound sessions are scoped artifacts of the contact drawer, not
    general chat history: they are excluded by default and returned only when
    an explicit ``contact_id`` is requested. This keeps them out of the global
    agent-chat history (where they would render with no agent).
    """
    try:
        query = db.query(ChatSession).filter(ChatSession.account_id == jwt['id'])

        # Optionally filter by agent_id
        if agent_id is not None:
            query = query.filter(ChatSession.agent_id == agent_id)

        # Contact-bound sessions are hidden unless explicitly requested.
        if contact_id is not None:
            query = query.filter(ChatSession.contact_id == contact_id)
        else:
            query = query.filter(ChatSession.contact_id.is_(None))

        sessions = query.order_by(ChatSession.created_at.desc()).offset(offset).limit(limit).all()

        sessions = [{
            "id": s.id,
            "sessionId": s.session_id,
            "agentId": s.agent_id,
            "accountId": s.account_id,
            "createdAt": s.created_at,
            "title": s.title,
            "contactId": s.contact_id
        } for s in sessions]

        return sessions
    except Exception as e:
        raise handle_db_error(e, "[OPERATION]")

@router.get("/sessions/{session_id}", response_model=ChatSessionWithMessagesResponse)
@limiter.limit("30/minute")
async def get_session(
    session_id: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """Get a specific session by session_id with its messages"""
    try:
        # Convert string to UUID for database query
        session_uuid = uuid.UUID(session_id)
        
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.account_id == jwt['id']
        ).first()
        
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
        # Get all messages for this session
        messages = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id
        ).order_by(ChatMessage.created_at.asc()).all()

        # Convert message fields to camelCase for each message
        def to_camel(s: str) -> str:
            parts = s.split('_')
            return parts[0] + ''.join(p.title() for p in parts[1:])

        def _normalize_content(content) -> str:
            """Coerce Anthropic-style content block lists to a plain string."""
            if isinstance(content, list):
                return "".join(
                    block.get("text", "") if isinstance(block, dict) else str(block)
                    for block in content
                )
            return content if isinstance(content, str) else str(content)

        def convert_shape_of_message(msg):

            message_data = {
                "id": msg.id,
                "role": msg.message['role'],
                "content": _normalize_content(msg.message['content']),
                "createdAt": msg.created_at
            }
            
            # Include toolCalls if present in the message
            if 'toolCalls' in msg.message and msg.message['toolCalls']:
                message_data["toolCalls"] = msg.message['toolCalls']
            
            return message_data

        messages = [convert_shape_of_message(m) for m in messages]
        
        # Create response with session and messages
        response_data = {
            "id": session.id,
            "sessionId": session.session_id,
            "agentId": session.agent_id,
            "accountId": session.account_id,
            "createdAt": session.created_at,
            "title": session.title,
            "contactId": session.contact_id,
            "messages": messages
        }
        
        return response_data
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise handle_db_error(e, "[OPERATION]")

@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def delete_session(
    session_id: str, 
    db: db_dependency, 
    jwt: jwt_dependency, 
    request: Request
):
    """Delete a session and all its messages"""
    try:
        # Convert string to UUID for database query
        session_uuid = uuid.UUID(session_id)
        
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.account_id == jwt['id']
        ).first()
        
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return None
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID format")
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[OPERATION]")

@router.delete("/sessions/{session_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("10/minute")
async def clear_session_messages(
    session_id: str, 
    db: db_dependency, 
    jwt: jwt_dependency, 
    request: Request
):
    """Clear all messages from a session without deleting the session itself"""
    try:
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid session ID format"
            )
        
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.account_id == jwt['id']
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Session not found"
            )
        
        deleted_count = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id
        ).delete()
        
        db.commit()
        
        logger.info("[CLEAR MESSAGES] Deleted %d messages from session %s", deleted_count, session_id)
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_db_error(e, "[CLEAR MESSAGES]")
