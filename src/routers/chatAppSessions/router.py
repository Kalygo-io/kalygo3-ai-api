from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from src.deps import db_dependency, jwt_dependency
from src.db.models import ChatAppSession, ChatAppMessage, Account
import uuid
from datetime import datetime

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

# Pydantic models for request/response
class ChatAppSessionCreate(BaseModel):
    chatAppId: str
    title: Optional[str] = None

class ChatAppSessionUpdate(BaseModel):
    title: Optional[str] = None

def to_camel(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(p.title() for p in parts[1:])

class ChatAppMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    createdAt: datetime

class ChatAppSessionResponse(BaseModel):
    id: int
    sessionId: uuid.UUID
    chatAppId: str
    accountId: int
    createdAt: datetime
    title: Optional[str] = None

class ChatAppSessionWithMessagesResponse(BaseModel):
    id: int
    sessionId: uuid.UUID
    chatAppId: str
    accountId: int
    createdAt: datetime
    title: Optional[str] = None
    messages: List[ChatAppMessageResponse] = []

    class Config:
        from_attributes = True
        alias_generator = to_camel

class ChatMessageCreate(BaseModel):
    message: dict

class ChatMessageResponse(BaseModel):
    id: int
    message: dict
    session_id: int
    created_at: datetime

    class Config:
        from_attributes = True

# CRUD Operations for ChatAppSession

@router.post("/sessions", response_model=ChatAppSessionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def create_session(
    sessionData: ChatAppSessionCreate, 
    db: db_dependency, 
    jwt: jwt_dependency, 
    request: Request
):
    """Create a new chat app session"""
    try:
        print('Create a new chat app session')

        # Generate a new UUID for the session
        session_uuid = str(uuid.uuid4())
        
        # Create the session
        new_session = ChatAppSession(
            session_id=session_uuid,
            chat_app_id=sessionData.chatAppId,
            account_id=jwt['id'],
            title=sessionData.title
        )
        
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        
        return {
            "id": new_session.id,
            "sessionId": new_session.session_id,
            "chatAppId": new_session.chat_app_id,
            "accountId": new_session.account_id,
            "createdAt": new_session.created_at,
            "title": new_session.title
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/sessions", response_model=List[ChatAppSessionResponse])
@limiter.limit("30/minute")
async def get_sessions(
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request,
    limit: int = 50,
    offset: int = 0
):
    """Get all sessions for the authenticated user, optionally filtered by chat_app_id"""
    try:
        query = db.query(ChatAppSession).filter(ChatAppSession.account_id == jwt['id'])
        
        sessions = query.order_by(ChatAppSession.created_at.desc()).offset(offset).limit(limit).all()

        sessions = [{
            "id": s.id,
            "sessionId": s.session_id,
            "chatAppId": s.chat_app_id,
            "accountId": s.account_id,
            "createdAt": s.created_at,
            "title": s.title
        } for s in sessions]

        return sessions
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/sessions/{session_id}", response_model=ChatAppSessionWithMessagesResponse)
@limiter.limit("30/minute")
async def get_session(
    session_id: str,
    db: db_dependency,
    jwt: jwt_dependency,
    request: Request
):
    """Get a specific session by session_id with its messages"""
    try:

        print('Get a specific session by session_id with its messages')

        # Convert string to UUID for database query
        session_uuid = uuid.UUID(session_id)
        
        session = db.query(ChatAppSession).filter(
            ChatAppSession.session_id == session_uuid,
            ChatAppSession.account_id == jwt['id']
        ).first()
        
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
        # Get all messages for this session
        messages = db.query(ChatAppMessage).filter(
            ChatAppMessage.chat_app_session_id == session.id
        ).order_by(ChatAppMessage.created_at.asc()).all()

        # Convert message fields to camelCase for each message
        def to_camel(s: str) -> str:
            parts = s.split('_')
            return parts[0] + ''.join(p.title() for p in parts[1:])

        def convert_shape_of_message(msg):
            
            print('convert_shape_of_message', msg)

            message_data = {
                "id": msg.id,
                "role": msg.message['role'],
                "content": msg.message['content'],
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
            "chatAppId": session.chat_app_id,
            "accountId": session.account_id,
            "createdAt": session.created_at,
            "title": session.title,
            "messages": messages
        }
        
        return response_data
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid session ID format")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# @router.put("/sessions/{session_id}", response_model=ChatAppSessionResponse)
# @limiter.limit("10/minute")
# async def update_session(
#     session_id: str,
#     session_data: ChatAppSessionUpdate,
#     db: db_dependency,
#     jwt: jwt_dependency,
#     request: Request
# ):
#     """Update a session's title"""
#     try:
#         session = db.query(ChatAppSession).filter(
#             ChatAppSession.session_id == session_id,
#             ChatAppSession.account_id == jwt['id']
#         ).first()
        
#         if not session:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
#         if session_data.title is not None:
#             session.title = session_data.title
        
#         db.commit()
#         db.refresh(session)
        
#         return session
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

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
        session = db.query(ChatAppSession).filter(
            ChatAppSession.session_id == session_id,
            ChatAppSession.account_id == jwt['id']
        ).first()
        
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
        db.delete(session)
        db.commit()
        
        return None
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# CRUD Operations for ChatMessage

# @router.post("/sessions/{session_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
# @limiter.limit("30/minute")
# async def create_message(
#     session_id: str, 
#     message_data: ChatMessageCreate, 
#     db: db_dependency, 
#     jwt: jwt_dependency, 
#     request: Request
# ):
#     """Add a message to a session"""
#     try:
#         # Verify the session exists and belongs to the user
#         session = db.query(ChatAppSession).filter(
#             ChatAppSession.session_id == session_id,
#             ChatAppSession.account_id == jwt['id']
#         ).first()
        
#         if not session:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
#         # Create the message
#         new_message = ChatMessage(
#             message=message_data.message,
#             session_id=session.id
#         )
        
#         db.add(new_message)
#         db.commit()
#         db.refresh(new_message)
        
#         return new_message
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# @router.get("/sessions/{session_id}/messages", response_model=List[ChatMessageResponse])
# @limiter.limit("30/minute")
# async def get_messages(
#     session_id: str, 
#     db: db_dependency, 
#     jwt: jwt_dependency, 
#     request: Request,
#     limit: int = 100,
#     offset: int = 0
# ):
#     """Get all messages for a session"""
#     try:
#         # Verify the session exists and belongs to the user
#         session = db.query(ChatAppSession).filter(
#             ChatAppSession.session_id == session_id,
#             ChatAppSession.account_id == jwt['id']
#         ).first()
        
#         if not session:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
#         messages = db.query(ChatMessage).filter(
#             ChatMessage.session_id == session.id
#         ).order_by(ChatMessage.created_at.asc()).offset(offset).limit(limit).all()
        
#         return messages
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# @router.get("/sessions/{session_id}/messages/{message_id}", response_model=ChatMessageResponse)
# @limiter.limit("30/minute")
# async def get_message(
#     session_id: str, 
#     message_id: int, 
#     db: db_dependency, 
#     jwt: jwt_dependency, 
#     request: Request
# ):
#     """Get a specific message from a session"""
#     try:
#         # Verify the session exists and belongs to the user
#         session = db.query(ChatAppSession).filter(
#             ChatAppSession.session_id == session_id,
#             ChatAppSession.account_id == jwt['id']
#         ).first()
        
#         if not session:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
#         message = db.query(ChatMessage).filter(
#             ChatMessage.id == message_id,
#             ChatMessage.session_id == session.id
#         ).first()
        
#         if not message:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        
#         return message
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# @router.delete("/sessions/{session_id}/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
# @limiter.limit("10/minute")
# async def delete_message(
#     session_id: str, 
#     message_id: int, 
#     db: db_dependency, 
#     jwt: jwt_dependency, 
#     request: Request
# ):
#     """Delete a specific message from a session"""
#     try:
#         # Verify the session exists and belongs to the user
#         session = db.query(ChatAppSession).filter(
#             ChatAppSession.session_id == session_id,
#             ChatAppSession.account_id == jwt['id']
#         ).first()
        
#         if not session:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        
#         message = db.query(ChatMessage).filter(
#             ChatMessage.id == message_id,
#             ChatMessage.session_id == session.id
#         ).first()
        
#         if not message:
#             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
        
#         db.delete(message)
#         db.commit()
        
#         return None
#     except HTTPException:
#         raise
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
