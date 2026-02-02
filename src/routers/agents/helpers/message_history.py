"""
Message history helpers for agent completion.

Handles building LangChain message history from database messages
and storing new messages to the database.
"""
from typing import List, Dict, Any, Optional
from langchain_community.chat_message_histories import ChatMessageHistory
from src.db.models import ChatMessage
from src.schemas import validate_against_schema


def build_message_history(db_messages: List[ChatMessage]) -> ChatMessageHistory:
    """
    Build a LangChain ChatMessageHistory from database messages.
    
    Args:
        db_messages: List of ChatMessage objects from the database
        
    Returns:
        ChatMessageHistory populated with the conversation history
    """
    message_history = ChatMessageHistory()
    
    for msg in db_messages:
        message_data = msg.message
        if isinstance(message_data, dict) and 'role' in message_data and 'content' in message_data:
            role = message_data['role']
            content = message_data['content']
            if role == 'human':
                message_history.add_user_message(content)
            elif role == 'ai':
                message_history.add_ai_message(content)
    
    return message_history


def store_user_message(
    db,
    session_id: int,
    prompt: str,
    pdf_filename: Optional[str] = None,
    validate: bool = True
) -> Optional[ChatMessage]:
    """
    Store a user message to the database.
    
    Args:
        db: Database session
        session_id: The chat session's internal ID (not UUID)
        prompt: The user's prompt text
        pdf_filename: Optional PDF filename if a PDF was attached
        validate: Whether to validate against schema
        
    Returns:
        The created ChatMessage, or None if storage failed
    """
    try:
        message_obj: Dict[str, Any] = {
            "role": "human",
            "content": prompt
        }
        
        # Add attachment metadata if PDF was included
        if pdf_filename:
            message_obj["attachments"] = [{
                "type": "pdf",
                "filename": pdf_filename
            }]
        
        # Validate message against schema
        if validate:
            try:
                validate_against_schema(message_obj, "message", 1)
            except Exception as validation_error:
                print(f"[MESSAGE HISTORY] Message validation error: {validation_error}")
                # Continue anyway - don't fail the request
        
        user_message = ChatMessage(
            message=message_obj,
            chat_session_id=session_id
        )
        db.add(user_message)
        db.commit()
        db.refresh(user_message)
        print(f"[MESSAGE HISTORY] Stored user message with ID: {user_message.id}")
        return user_message
        
    except Exception as e:
        print(f"[MESSAGE HISTORY] Failed to store user message: {e}")
        db.rollback()
        return None


def store_ai_message(
    db,
    session_id: int,
    content: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    validate: bool = True
) -> Optional[ChatMessage]:
    """
    Store an AI message to the database.
    
    Args:
        db: Database session
        session_id: The chat session's internal ID (not UUID)
        content: The AI's response content
        tool_calls: Optional list of tool calls made during the response
        validate: Whether to validate against schema
        
    Returns:
        The created ChatMessage, or None if storage failed
    """
    try:
        message_obj: Dict[str, Any] = {
            "role": "ai",
            "content": content
        }
        
        # Add tool calls if any
        if tool_calls:
            message_obj["toolCalls"] = tool_calls
        
        # Validate message against schema v2
        if validate:
            try:
                validate_against_schema(message_obj, "chat_message", 2)
            except Exception as validation_error:
                print(f"[MESSAGE HISTORY] Message validation error: {validation_error}")
                # Continue anyway - don't fail the request
        
        ai_message = ChatMessage(
            message=message_obj,
            chat_session_id=session_id
        )
        db.add(ai_message)
        db.commit()
        db.refresh(ai_message)
        print(f"[MESSAGE HISTORY] Stored AI response with ID: {ai_message.id}")
        return ai_message
        
    except Exception as e:
        print(f"[MESSAGE HISTORY] Failed to store AI response: {e}")
        db.rollback()
        return None
