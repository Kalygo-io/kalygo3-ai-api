from typing import List
import uuid
from fastapi import APIRouter, HTTPException, Request, status

from src.db.models import ChatAppMessage, ChatAppSession

from .tools import gptuesday_tool, tad_tool
from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt

from slowapi import Limiter
from slowapi.util import get_remote_address

import json
import os

from fastapi.responses import StreamingResponse

from langchain.callbacks import LangChainTracer
from langsmith import Client
from langchain import hub
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory

from .tools.calculator_tool import calculator_tool

from src.deps import db_dependency, jwt_dependency

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv

load_dotenv()

# Set LANGCHAIN_API_KEY from LANGSMITH_API_KEY if not already set (they're the same)
if not os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

callbacks = [
  LangChainTracer(
    project_name="re-act-agent",
    client=Client(
      api_url=os.getenv("LANGSMITH_ENDPOINT"),
      api_key=os.getenv("LANGSMITH_API_KEY")
    )
  )
]

router = APIRouter()

async def generator(sessionId: str, prompt: str, db, jwt):
    llm = ChatOpenAI(
        temperature=0, 
        streaming=True, 
        stream_usage=True,  # Enable token usage tracking during streaming
        model="gpt-4o-mini"
    )

    #v#v#v#
    try:
        # Convert string to UUID for database query
        session_uuid = uuid.UUID(sessionId)
        
        # Verify the session exists and belongs to the user
        session = db.query(ChatAppSession).filter(
            ChatAppSession.session_id == session_uuid,
            ChatAppSession.account_id == jwt['id']
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
        db_messages = db.query(ChatAppMessage).filter(
            ChatAppMessage.chat_app_session_id == session.id
        ).order_by(ChatAppMessage.created_at.asc()).all()
        
        print(f"Found {len(db_messages)} existing messages for session {sessionId}")
        
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
    #^#^#

    #v#v#v#
    message_history = ChatMessageHistory()
    for msg in db_messages:
        message_data = msg.message
        # Assuming message structure has 'role' and 'content' fields
        if isinstance(message_data, dict) and 'role' in message_data and 'content' in message_data:
            message_history.add_message(
                {"role": message_data['role'], "content": message_data['content']}
            )
    #^#^#^#

    prompt_template = hub.pull("hwchase17/openai-tools-agent") # Get the prompt to use - you can modify this!
    # tools = [serp_tool, gptuesday_tool]
    # tools = [gptuesday_tool, tad_tool]
    # tools = [reflect_tool, deliberate_tool]
    tools = [calculator_tool]
    
    agent = create_openai_tools_agent(
        llm.with_config({"tags": ["agent_llm"]}), tools, prompt_template
    )
    
    memory = ConversationBufferMemory(
        memory_key="chat_history", chat_memory=message_history, return_messages=True, output_key="output"
    )

    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, max_iterations=8).with_config(
        {
            "run_name": "Agent",
            "callbacks": callbacks
        }
    )

    # EVENTS <!-- https://python.langchain.com/docs/expression_language/streaming/#event-reference -->
    # on_chat_model_start, on_chat_model_stream, on_chat_model_end, on_llm_start, on_llm_stream, on_llm_end, on_chain_start, on_chain_stream, on_chain_end
    # on_tool_start, on_tool_stream, on_tool_end, on_retriever_start, on_retriever_chunk, on_retriever_end, on_prompt_start, on_prompt_end

    async for event in agent_executor.astream_events(
        {"input": prompt},
        version="v1",
    ):
        kind = event["event"]
        if kind == "on_chain_start":
            if (
                event["name"] == "Agent"
            ):  # Was assigned when creating the agent with `.with_config({"run_name": "Agent"})`
                print(
                    f"Starting agent: {event['name']} with input: {event['data'].get('input')}"
                )

                yield json.dumps({
                    "event": "on_chain_start",
                }, separators=(',', ':'))
        elif kind == "on_chain_end":
            if (
                event["name"] == "Agent"
            ):  # Was assigned when creating the agent with `.with_config({"run_name": "Agent"})`
                content = event['data'].get('output')['output']
                print()
                print("--")
                print(
                    f"Done agent: {event['name']} with output: {event['data'].get('output')['output']}"
                )
                
                if content:
                # Empty content in the context of OpenAI means
                # that the model is asking for a tool to be invoked.
                # So we only print non-empty content
                    try: # Store the AI's response into the session message history
                        ai_message = ChatAppMessage(
                            message={
                                "role": "ai",
                                "content": content
                            },
                            chat_app_session_id=session.id
                        )
                        db.add(ai_message)
                        db.commit()
                        db.refresh(ai_message)
                        print(f"Stored AI response with ID: {ai_message.id}")
                    except Exception as e:
                        print(f"Failed to store AI response: {e}")
                        db.rollback()

                    # print(content, end="|")

                    yield json.dumps({
                        "event": "on_chain_end",
                        "data": content
                    }, separators=(',', ':'))
        if kind == "on_chat_model_start":
            try: # Store the latest prompt into the session message history
                user_message = ChatAppMessage(
                    message={
                        "role": "human",
                        "content": prompt
                    },
                    chat_app_session_id=session.id
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
                "event": "on_chat_model_start",
            }, separators=(',', ':'))
        elif kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                # Empty content in the context of OpenAI means
                # that the model is asking for a tool to be invoked.
                # So we only print non-empty content
                print(content, end="|")
                yield json.dumps({
                    "event": "on_chat_model_stream",
                    "data": content
                }, separators=(',', ':'))
        elif kind == "on_chat_model_end":
            print("!!! on_chat_model_end !!!") # It seems that `on_chat_model_end` is not a relevant event for this `agent_executor` abstraction
        elif kind == "on_tool_start":
            print("--")
            print(
                f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}"
            )
            yield json.dumps({
                "event": "on_tool_start",
                "data": f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}"
            }, separators=(',', ':'))
        elif kind == "on_tool_end":
            print(f"Done tool: {event['name']}")
            print(f"Tool output was: {event['data'].get('output')}")
            print("--")
            yield json.dumps({
                "event": "on_tool_end",
            }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(chatSessionPrompt: ChatSessionPrompt, jwt: jwt_dependency, db: db_dependency, request: Request):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="This endpoint is not yet implemented"
    )

    # return StreamingResponse(generator(chatSessionPrompt.sessionId, chatSessionPrompt.prompt, db, jwt), media_type='text/event-stream')