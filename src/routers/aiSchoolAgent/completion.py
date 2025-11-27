from datetime import datetime
from typing import List
import uuid
from fastapi import APIRouter, HTTPException, Request, status

from src.db.models import ChatAppMessage, ChatAppSession, Account
from src.clients.stripe_client import get_payment_methods
import stripe

from .tools import ai_school_reranking_tool
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
from langchain_ollama import ChatOllama
from langchain.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory

from src.deps import db_dependency, jwt_dependency

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

load_dotenv()

# Set LANGCHAIN_API_KEY from LANGSMITH_API_KEY if not already set (they're the same)
if not os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

callbacks = [
  LangChainTracer(
    project_name="ai-school-agent",
    client=Client(
      api_url=os.getenv("LANGSMITH_ENDPOINT"),
      api_key=os.getenv("LANGSMITH_API_KEY")
    )
  )
]

router = APIRouter()

def get_prompt_template(current_date_time: str):
    """Get the prompt template from LangChain Hub with fallback to default."""
    # try:
    #     return hub.pull("hwchase17/openai-tools-agent")
    # except Exception as e:
    # print(f"Warning: Failed to pull prompt from LangChain Hub: {e}")
    print("Using default prompt template instead.")
    # Default prompt template for OpenAI tools agent
    return ChatPromptTemplate.from_messages([
        ("system", f"You are a helpful assistant. Use the provided tools to answer questions. Do not hallucinate. Ground your knowledge deeply in the knowledge base, and if you are unsure When responding to inputs, ask for clarification. The current date and time is {current_date_time}."),
        MessagesPlaceholder(variable_name="chat_history"),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

async def generator(sessionId: str, prompt: str, db, jwt):
    # ============================================================
    # Payment verification: Check for Stripe customer ID and payment method
    # ============================================================
    try:
        # Get the account from the database
        account_id = int(jwt['id']) if isinstance(jwt['id'], str) else jwt['id']
        account = db.query(Account).filter(Account.id == account_id).first()
        
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "error": "Account not found",
                    "message": "Your account could not be found.",
                    "hint": "Please contact support if this issue persists."
                }
            )
        
        # Check if account has a Stripe customer ID
        if not account.stripe_customer_id:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "error": "Payment method required",
                    "message": "Please add a payment method to your account to use this service.",
                    "hint": "You can add a payment method in your account settings."
                }
            )
        
        # Check if the Stripe customer has at least one payment method
        try:
            payment_methods = get_payment_methods(account.stripe_customer_id)
            if not payment_methods or len(payment_methods) == 0:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "error": "Payment method required",
                        "message": "Please add a payment method to your account to use this service.",
                        "hint": "You can add a payment method in your account settings."
                    }
                )
        except stripe.error.StripeError as e:
            print(f"Stripe error checking payment methods: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "error": "Payment verification failed",
                    "message": "Unable to verify payment method. Please try again later.",
                    "hint": str(e)
                }
            )
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error verifying payment: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Payment verification error",
                "message": "An error occurred while verifying your payment method.",
                "hint": str(e)
            }
        )
    # ============================================================
    
    llm = ChatOpenAI(
        temperature=0, 
        streaming=True, 
        stream_usage=True,  # Enable token usage tracking during streaming
        model="gpt-4o-mini",
    )

    # llm = ChatOllama(
    #     model="qwen2.5:3b",  # The model name as shown in `ollama list`
    #     base_url="http://host.docker.internal:11434",  # Default Ollama server URL
    #     temperature=0,  # Control randomness (0 = deterministic, higher = more creative)
    # )

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
    
    # Prevent duplicate: Remove the last message if it matches the current prompt
    # ConversationBufferMemory will automatically add the current input, so we don't want it duplicated
    if message_history.messages:
        last_message = message_history.messages[-1]
        # Check if last message is a human message with the same content as current prompt
        if (hasattr(last_message, 'content') and last_message.content == prompt and 
            hasattr(last_message, 'type') and last_message.type == 'human'):
            # Remove the duplicate - ConversationBufferMemory will add it when agent_executor runs
            message_history.messages.pop()
            print(f"Removed duplicate prompt from memory: {prompt[:50]}...")
    #^#^#^#

    prompt_template = get_prompt_template(current_date_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    print("--------------------------------")
    print("--------------------------------")
    print(prompt_template)
    print("--------------------------------")
    print("--------------------------------")

    tools = [ai_school_reranking_tool]

    llm.bind_tools(tools)
    
    retrieval_calls = [] # Track retrieval calls

    agent = create_openai_tools_agent(
        llm.with_config({"tags": ["agent_llm"]}), tools, prompt_template
    )
        
    memory = ConversationBufferMemory(
        memory_key="chat_history", chat_memory=message_history, return_messages=True, output_key="output"
    )

    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory, max_iterations=10).with_config(
        {
            "run_name": "Agent",
            "callbacks": callbacks
        }
    )

    # EVENTS <!-- https://python.langchain.com/docs/expression_language/streaming/#event-reference -->
    # on_chat_model_start, on_chat_model_stream, on_chat_model_end, on_llm_start, on_llm_stream, on_llm_end, on_chain_start, on_chain_stream, on_chain_end
    # on_tool_start, on_tool_stream, on_tool_end, on_retriever_start, on_retriever_chunk, on_retriever_end, on_prompt_start, on_prompt_end

    # Track if we've already stored the user message to prevent duplicates
    user_message_stored = False
    
    async for event in agent_executor.astream_events(
        {
            "input": prompt
        },
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
                    f"Done agent: {event['name']}"
                )
                print(len(retrieval_calls))
                
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
                        "data": content,
                        "retrieval_calls": retrieval_calls
                    }, separators=(',', ':'))
        if kind == "on_chat_model_start":
            # Only store the user message once, even if on_chat_model_start fires multiple times
            # (which happens when the agent makes multiple LLM calls for tool usage)
            if not user_message_stored:
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
                    user_message_stored = True
                except Exception as e:
                    print(f"Failed to store user message: {e}")
                    db.rollback()
            
            yield json.dumps({
                "event": "on_chat_model_start",
                "retrieval_calls": retrieval_calls
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
            
            # Track retrieval calls if it's the retrieval_with_reranking tool
            if event['name'] == "ai_school_reranking_tool":
                tool_input = event['data'].get('input', {})
                tool_output = event['data'].get('output', {})
                
                # Extract query from tool input
                query = tool_input.get('query', 'Unknown query')
                
                # Extract results from tool output
                reranked_results = tool_output.get('reranked_results', [])
                
                # Format results for response
                formatted_results = []
                for result in reranked_results:

                    formatted_results.append({
                        "chunk_id": result.get("metadata", {}).get("chunk_id", "N/A"),
                        "total_chunks": result.get("metadata", {}).get("total_chunks", "N/A"),
                        "relevance_score": result.get("relevance_score", 0.0),
                        "similarity_score": result.get("similarity_score", 0.0),
                        "content": result.get("metadata", {}).get("content", ""),
                        "filename": result.get("metadata", {}).get("filename", "N/A")
                    })
                
                retrieval_calls.append({
                    "query": query,
                    "reranked_results": formatted_results,
                    "message": tool_output.get('message', ''),
                    "namespace": tool_output.get('namespace', '')
                })
            
            yield json.dumps({
                "event": "on_tool_end",
            }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: ChatSessionPrompt, jwt: jwt_dependency, db: db_dependency, request: Request):
    return StreamingResponse(generator(prompt.sessionId, prompt.prompt, db, jwt), media_type='text/event-stream')