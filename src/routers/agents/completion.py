"""
Agent completion endpoint - dynamically configures agents based on agent config.

Supports:
- Streaming responses via Server-Sent Events (SSE)
- Tool-using agents (RAG, database tools, etc.)
- Simple chat agents (no tools)
- PDF document attachments (vision or text extraction mode)
"""
from typing import Optional
import uuid
import os
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from src.deps import db_dependency, auth_dependency
from src.db.models import Agent, ChatSession, ChatMessage, Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import get_credential_value
from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tracers import LangChainTracer
from langsmith import Client

# Import tool factory
from src.tools import create_tools_from_agent_config, CredentialError

# Import PDF processing support
from src.utils.pdf_to_images import build_pdf_message

# Import helpers
from src.routers.agents.helpers import (
    build_message_history,
    store_user_message,
    store_ai_message,
    extract_auth_token,
    format_tool_call,
    sse_event,
    sse_error,
    get_model_config,
    create_llm,
    get_required_credential_type,
)

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

load_dotenv()

# Set LANGCHAIN_API_KEY from LANGSMITH_API_KEY if not already set
if not os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

# Initialize LangSmith callbacks if configured
callbacks = [
    LangChainTracer(
        project_name="dynamic-agent",
        client=Client(
            api_url=os.getenv("LANGSMITH_ENDPOINT"),
            api_key=os.getenv("LANGSMITH_API_KEY")
        )
    )
] if os.getenv("LANGSMITH_API_KEY") else []


async def generator(
    agent_id: int,
    session_id: str,
    prompt: str,
    db,
    auth: dict,
    request: Request = None,
    pdf_base64: Optional[str] = None,
    pdf_filename: Optional[str] = None,
    pdf_use_vision: bool = False
):
    """
    Generator function for streaming agent completion.
    
    Dynamically configures agent based on agent config from database.
    Supports optional PDF attachment (vision or text extraction mode).
    
    Args:
        agent_id: The agent's database ID
        session_id: The chat session UUID string
        prompt: The user's prompt text
        db: Database session
        auth: Authentication info dict
        request: FastAPI request object
        pdf_base64: Optional base64-encoded PDF content
        pdf_filename: Optional PDF filename
        pdf_use_vision: If True, use vision mode; if False, use text extraction
    """
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        
        # ─────────────────────────────────────────────────────────────────────
        # 1. Load and validate agent
        # ─────────────────────────────────────────────────────────────────────
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id
        ).first()
        
        if not agent:
            yield sse_error("Agent not found", "The specified agent was not found or does not belong to you.")
            return
        
        if not agent.config:
            print(f"[AGENT COMPLETION] Agent {agent_id} has no config")
            yield sse_error("Invalid agent configuration", "Agent configuration is missing.")
            return
        
        config_data = agent.config.get('data', {})
        config_version = agent.config.get('version', 1)
        system_prompt_raw = config_data.get('systemPrompt', 'You are a helpful assistant.')
        
        # Escape curly braces in system prompt to prevent LangChain template interpretation
        # This allows system prompts to contain JSON examples, code snippets, etc.
        system_prompt = system_prompt_raw.replace("{", "{{").replace("}", "}}")
        
        # Log config info
        tool_count = len(config_data.get('knowledgeBases' if config_version == 1 else 'tools', []))
        print(f"[AGENT COMPLETION] Config v{config_version} - system_prompt length: {len(system_prompt)}, tools: {tool_count}")
        
        # ─────────────────────────────────────────────────────────────────────
        # 2. Get model configuration and credentials
        # ─────────────────────────────────────────────────────────────────────
        model_config = get_model_config(agent.config)
        provider = model_config['provider']
        model_name = model_config['model']
        print(f"[AGENT COMPLETION] Using model: {provider}/{model_name}")
        
        # Get the required credential for this provider
        required_credential_type = get_required_credential_type(provider)
        credentials = {}
        
        if required_credential_type:
            credential = db.query(Credential).filter(
                Credential.account_id == account_id,
                Credential.service_name == required_credential_type
            ).first()
            
            if not credential:
                yield sse_error(
                    f"{provider.title()} API key required", 
                    f"Please add your {provider.title()} API key in account settings to use {model_name}."
                )
                return
            
            try:
                api_key = get_credential_value(credential, "api_key")
                credentials[provider] = api_key
            except Exception as e:
                yield sse_error("Failed to retrieve API key", str(e))
                return
        
        # ─────────────────────────────────────────────────────────────────────
        # 3. Initialize LLM
        # ─────────────────────────────────────────────────────────────────────
        try:
            llm, llm_provider = create_llm(
                model_config=model_config,
                credentials=credentials,
                streaming=True,
                temperature=0,
            )
            print(f"[AGENT COMPLETION] Initialized {llm_provider} LLM: {model_name}")
        except ValueError as e:
            yield sse_error("LLM initialization failed", str(e))
            return
        
        # ─────────────────────────────────────────────────────────────────────
        # 4. Get or create chat session
        # ─────────────────────────────────────────────────────────────────────
        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            yield sse_error("Invalid sessionId format", "The sessionId must be a valid UUID format.")
            return
        
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_uuid,
            ChatSession.account_id == account_id
        ).first()
        
        # Auto-create session if it doesn't exist
        if not session:
            print(f"[AGENT COMPLETION] Session {session_id} not found, creating automatically...")
            try:
                session = ChatSession(
                    session_id=session_uuid,
                    agent_id=agent_id,
                    account_id=account_id,
                    title=f"Chat with Agent {agent_id}"
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                print(f"[AGENT COMPLETION] Created new session with ID: {session.id}")
            except Exception as e:
                db.rollback()
                print(f"[AGENT COMPLETION] Failed to create session: {e}")
                yield sse_error("Failed to create session", f"Could not create chat session: {str(e)}")
                return
        
        # ─────────────────────────────────────────────────────────────────────
        # 5. Build message history from database
        # ─────────────────────────────────────────────────────────────────────
        db_messages = db.query(ChatMessage).filter(
            ChatMessage.chat_session_id == session.id
        ).order_by(ChatMessage.created_at.asc()).all()
        
        message_history = build_message_history(db_messages)
        
        # ─────────────────────────────────────────────────────────────────────
        # 6. Create tools from agent config
        # ─────────────────────────────────────────────────────────────────────
        auth_token = extract_auth_token(request, auth)
        
        try:
            tools = await create_tools_from_agent_config(
                agent_config=agent.config,
                account_id=account_id,
                db=db,
                auth_token=auth_token,
                request=request,
                chat_session_id=session_uuid
            )
        except CredentialError as e:
            print(f"[AGENT COMPLETION] Tool configuration error: {e}")
            yield sse_error("Tool configuration error", str(e))
            return
        except ValueError as e:
            print(f"[AGENT COMPLETION] Tool configuration error: {e}")
            yield sse_error("Invalid tool configuration", str(e))
            return
        
        print(f"[AGENT COMPLETION] Created {len(tools)} tools, using {'agent executor' if tools else 'simple chat'} mode")
        
        # ─────────────────────────────────────────────────────────────────────
        # 7. Create agent or prompt template
        # ─────────────────────────────────────────────────────────────────────
        if tools:
            # Agent with tools (RAG agent)
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad")
            ])
            llm_with_tools = llm.bind_tools(tools)
            agent_langchain = create_openai_tools_agent(
                llm_with_tools.with_config({"tags": ["agent_llm"]}),
                tools,
                prompt_template
            )
            print(f"[AGENT COMPLETION] Agent created with {len(tools)} tools bound to LLM")
        else:
            # Simple chat agent without tools
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ])
            agent_langchain = None
        
        # ─────────────────────────────────────────────────────────────────────
        # 8. Create memory and agent executor
        # ─────────────────────────────────────────────────────────────────────
        memory = ConversationBufferMemory(
            memory_key="chat_history",
            chat_memory=message_history,
            return_messages=True,
            output_key="output" if tools else None
        )
        
        user_email = auth.get('email', 'unknown')
        
        if tools:
            agent_executor = AgentExecutor(
                agent=agent_langchain,
                tools=tools,
                memory=memory,
                max_iterations=10
            ).with_config({
                "run_name": "Agent",
                "callbacks": callbacks,
                "metadata": {
                    "user_email": user_email,
                    "agent_id": agent_id,
                    "session_id": str(session_uuid)
                },
                "tags": [f"user:{user_email}", f"agent:{agent_id}"]
            })
            print(f"[AGENT COMPLETION] Agent executor created with {len(tools)} tools")
        else:
            agent_executor = None
        
        # ─────────────────────────────────────────────────────────────────────
        # 9. Build input (with optional PDF)
        # ─────────────────────────────────────────────────────────────────────
        if pdf_base64:
            agent_input = build_pdf_message(
                prompt=prompt,
                pdf_base64=pdf_base64,
                pdf_filename=pdf_filename,
                use_vision=pdf_use_vision,
                max_pages=10 if pdf_use_vision else 50
            )
            mode = "vision" if pdf_use_vision else "text extraction"
            print(f"[AGENT COMPLETION] Built PDF message using {mode} mode")
        else:
            agent_input = prompt
        
        # ─────────────────────────────────────────────────────────────────────
        # 10. Stream completion
        # ─────────────────────────────────────────────────────────────────────
        user_message_stored = False
        tool_calls = []
        
        if agent_executor:
            # Stream with agent executor (has tools)
            async for event_data in _stream_agent_executor(
                agent_executor=agent_executor,
                agent_input=agent_input,
                prompt=prompt,
                pdf_filename=pdf_filename,
                db=db,
                session=session,
                tool_calls=tool_calls,
                user_message_stored=user_message_stored
            ):
                yield event_data
        else:
            # Stream simple chat (no tools)
            async for event_data in _stream_simple_chat(
                llm=llm,
                prompt_template=prompt_template,
                message_history=message_history,
                agent_input=agent_input,
                prompt=prompt,
                pdf_filename=pdf_filename,
                db=db,
                session=session,
                callbacks=callbacks
            ):
                yield event_data
                
    except Exception as e:
        print(f"[AGENT COMPLETION] Fatal error in generator: {e}")
        import traceback
        traceback.print_exc()
        yield sse_error("Internal server error", str(e))


async def _stream_agent_executor(
    agent_executor,
    agent_input,
    prompt: str,
    pdf_filename: Optional[str],
    db,
    session,
    tool_calls: list,
    user_message_stored: bool
):
    """
    Stream events from an agent executor with tools.
    
    This is an internal generator that handles the agent executor streaming loop.
    """
    print(f"[AGENT COMPLETION] Streaming events from agent executor")
    print(f"[AGENT COMPLETION] Prompt: {prompt[:100]}...")
    
    async for event in agent_executor.astream_events(
        {"input": agent_input},
        version="v1",
    ):
        kind = event["event"]
        
        if kind == "on_chain_start":
            if event["name"] == "Agent":
                print(f"Starting agent: {event['name']}")
                yield sse_event("on_chain_start")
                
        elif kind == "on_chain_end":
            if event["name"] == "Agent":
                content = event['data'].get('output', {}).get('output', '')
                print(f"Done agent: {event['name']}, tool_calls: {len(tool_calls)}")
                
                if content:
                    # Store AI response
                    store_ai_message(db, session.id, content, tool_calls if tool_calls else None)
                    yield sse_event("on_chain_end", data=content, tool_calls=tool_calls)
                    
        elif kind == "on_chat_model_start":
            if not user_message_stored:
                store_user_message(db, session.id, prompt, pdf_filename)
                user_message_stored = True
            yield sse_event("on_chat_model_start", tool_calls=tool_calls)
            
        elif kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                print(content, end="|", flush=True)
                yield sse_event("on_chat_model_stream", data=content)
                
        elif kind == "on_tool_start":
            print(f"⚡ Starting tool: {event['name']}")
            yield sse_event("on_tool_start", data=f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}")
            
        elif kind == "on_tool_end":
            print(f"✅ Tool finished: {event['name']}")
            
            # Format and track tool call
            formatted = format_tool_call(
                tool_name=event['name'],
                tool_input=event['data'].get('input', {}),
                tool_output=event['data'].get('output', {})
            )
            if formatted:
                tool_calls.append(formatted)
            
            yield sse_event("on_tool_end")


async def _stream_simple_chat(
    llm,
    prompt_template,
    message_history,
    agent_input,
    prompt: str,
    pdf_filename: Optional[str],
    db,
    session,
    callbacks: list
):
    """
    Stream a simple chat completion without tools.
    
    This is an internal generator that handles simple LLM streaming.
    """
    print(f"[AGENT COMPLETION] Using simple chat mode (no tools)")
    
    # Store user message
    store_user_message(db, session.id, prompt, pdf_filename)
    
    yield sse_event("on_chat_model_start")
    
    print(f"[AGENT COMPLETION] Streaming with history of {len(message_history.messages)} messages")
    
    full_response = ""
    chunk_count = 0
    
    try:
        # Prepare input - handle both string and HumanMessage
        if isinstance(agent_input, str):
            formatted_input = prompt_template.format_messages(
                chat_history=message_history.messages,
                input=agent_input
            )
        else:
            # For multimodal messages (PDF), we need to handle differently
            # Replace the human message placeholder with our multimodal message
            messages = [
                ("system", prompt_template.messages[0].prompt.template),
            ]
            for msg in message_history.messages:
                messages.append(msg)
            messages.append(agent_input)  # Our HumanMessage with PDF content
            formatted_input = messages
        
        config = {"callbacks": callbacks} if callbacks else {}
        
        async for event in llm.astream_events(
            formatted_input,
            version="v1",
            config=config
        ):
            if event["event"] == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content:
                    chunk_count += 1
                    full_response += content
                    yield sse_event("on_chat_model_stream", data=content)
        
        print(f"[AGENT COMPLETION] Finished - {chunk_count} chunks, {len(full_response)} chars")
        
    except Exception as e:
        print(f"[AGENT COMPLETION] Error during streaming: {e}")
        import traceback
        traceback.print_exc()
        yield sse_error("Streaming error", str(e))
        return
    
    # Store AI response
    if full_response:
        store_ai_message(db, session.id, full_response)
    
    yield sse_event("on_chain_end", data=full_response)


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoint
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/{agent_id}/completion")
@limiter.limit("10/minute")
async def agent_completion(
    agent_id: int,
    request_body: ChatSessionPrompt,
    db: db_dependency,
    auth: auth_dependency,
    request: Request
):
    """
    Stream completion from a dynamically configured agent.
    
    The agent is configured based on its config stored in the database.
    Supports optional PDF attachments for document-based queries.
    
    Args:
        agent_id: The agent's database ID
        request_body: The request containing prompt, sessionId, and optional PDF
        
    Request Body:
        - prompt: The user's message/question
        - sessionId: UUID of the chat session
        - pdf: Optional base64-encoded PDF content
        - pdfFilename: Optional filename for the PDF
        - pdfUseVision: If true, use vision mode (images); if false, use text extraction
        
    Returns:
        StreamingResponse with Server-Sent Events
    """
    print(f"[AGENT COMPLETION] Received request for agent_id: {agent_id}")
    print(f"[AGENT COMPLETION] sessionId={request_body.sessionId}, prompt={request_body.prompt[:50]}...")
    if request_body.pdf:
        print(f"[AGENT COMPLETION] PDF attached: {request_body.pdfFilename}, vision={request_body.pdfUseVision}")
    
    return StreamingResponse(
        generator(
            agent_id=agent_id,
            session_id=request_body.sessionId,
            prompt=request_body.prompt,
            db=db,
            auth=auth,
            request=request,
            pdf_base64=request_body.pdf,
            pdf_filename=request_body.pdfFilename,
            pdf_use_vision=request_body.pdfUseVision or False
        ),
        media_type='text/event-stream'
    )
