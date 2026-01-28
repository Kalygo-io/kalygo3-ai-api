from typing import List
from fastapi import APIRouter, Request, HTTPException, status
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_postgres import PostgresChatMessageHistory

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt

import json
import os
import uuid
from datetime import datetime

from fastapi.responses import StreamingResponse

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tracers import LangChainTracer
from langsmith import Client
import psycopg
from src.deps import jwt_dependency, db_dependency
from src.db.models import ChatSession, ChatMessage

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv

load_dotenv()

callbacks = [
  LangChainTracer(
    project_name="persistent-memory",
    client=Client(
      api_url=os.getenv("LANGSMITH_ENDPOINT"),
      api_key=os.getenv("LANGSMITH_API_KEY")
    )
  )
]

router = APIRouter()

async def generator(chatSessionPrompt: ChatSessionPrompt, db, jwt):
    
    # model: str = "gpt-4o-mini"
    # llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"))
    model: str = "claude-3-5-sonnet-20240620"
    llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)

    try:
        # Convert string to UUID for database query
        session_uuid = uuid.UUID(chatSessionPrompt.sessionId)
        
        # Verify the session exists and belongs to the user
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.account_id == jwt['id']
        ).first()
        
        if not session:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "Session not found",
                    "message": "The specified session was not found or does not belong to you.",
                    "hint": "Please check the sessionId or create a new session."
                }
            )
        
        # Get all messages for this session from chat_app_messages table
        db_messages = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        print(f"Found {len(db_messages)} existing messages for session {chatSessionPrompt.sessionId}")
        
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid sessionId format",
                "message": "The sessionId must be a valid UUID format.",
                "hint": "Please provide a valid UUID for the sessionId."
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Database error",
                "message": "Failed to retrieve session messages.",
                "hint": str(e)
            }
        )

    system_message = [("human", "You're an assistant. Bold key terms in your responses.")]
    
    # Convert database messages to chat format
    chat_history_messages = []
    for msg in db_messages:
        message_data = msg.message
        # Assuming message structure has 'role' and 'content' fields
        if isinstance(message_data, dict) and 'role' in message_data and 'content' in message_data:
            chat_history_messages.append((message_data['role'], message_data['content']))
    
    # Add the current prompt
    all_messages = system_message + chat_history_messages + [("human", chatSessionPrompt.prompt)]
    
    # Variables to store messages for database
    user_message_id = None
    ai_response_content = ""
    
    async for evt in llm.astream_events(all_messages, version="v1", config={"callbacks": callbacks}, model=model):
        if evt["event"] == "on_chat_model_start":
            try: # Store the latest prompt into the session message history
                user_message = ChatMessage(
                    message={
                        "role": "human",
                        "content": chatSessionPrompt.prompt
                    },
                    chat_session_id=session.id
                )
                db.add(user_message)
                db.commit()
                db.refresh(user_message)
                user_message_id = user_message.id
                print(f"Stored user message with ID: {user_message_id}")
            except Exception as e:
                print(f"Failed to store user message: {e}")
                db.rollback()
            
            yield json.dumps({
                "event": "on_chat_model_start"
            }, separators=(',', ':'))

        elif evt["event"] == "on_chat_model_stream":
            # Accumulate AI response content
            ai_response_content += evt["data"]['chunk'].content
            
            yield json.dumps({
                "event": "on_chat_model_stream",
                "data": evt["data"]['chunk'].content
            }, separators=(',', ':'))

        elif evt["event"] == "on_chat_model_end":
            try: # Store the AI's response into the session message history
                ai_message = ChatMessage(
                    message={
                        "role": "ai",
                        "content": ai_response_content
                    },
                    chat_session_id=session.id
                )
                db.add(ai_message)
                db.commit()
                db.refresh(ai_message)
                print(f"Stored AI response with ID: {ai_message.id}")
            except Exception as e:
                print(f"Failed to store AI response: {e}")
                db.rollback()
            
            yield json.dumps({
                "event": "on_chat_model_end",
                "data": evt["data"]['output'].content
            }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
async def prompt(chatSessionPrompt: ChatSessionPrompt, jwt: jwt_dependency, db: db_dependency, request: Request):

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="This endpoint is not yet implemented"
    )

    print('chatSessionPrompt.sessionId', chatSessionPrompt.sessionId)

    # Guard clause: Check if sessionId is provided
    if not getattr(chatSessionPrompt, "sessionId", None):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Missing sessionId",
                "message": "A valid sessionId must be provided to continue the chat session.",
                "hint": "Please ensure your request includes a sessionId field."
            }
        )

    
    # Convert string to UUID for database query
    session_uuid = uuid.UUID(chatSessionPrompt.sessionId)
    
    # Verify the session exists and belongs to the user
    session = db.query(ChatSession).filter(
        ChatSession.session_id == session_uuid,
        ChatSession.account_id == jwt['id']
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Session not found",
                "message": "The specified session was not found or does not belong to you.",
                "hint": "Please check the sessionId or create a new session."
            }
        )
        
    return StreamingResponse(generator(chatSessionPrompt, db, jwt), media_type='text/event-stream')