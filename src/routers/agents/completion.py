"""
Agent completion endpoint - dynamically configures agents based on agent config.

Supports:
- Streaming responses via Server-Sent Events (SSE)
- Tool-using agents (RAG, database tools, etc.)
- Simple chat agents (no tools)
- PDF document attachments (vision or text extraction mode)
"""
from typing import Optional
import time
import uuid
import os
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import OperationalError
from src.deps import db_dependency, auth_dependency
from src.db.database import SessionLocal
from src.db.models import Agent, ChatSession, ChatMessage, Credential
from src.services.agent_access import can_access_agent
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import get_credential_value
from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv

from src.utils.template_variables import resolve_template_variables, build_variable_context
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tracers import LangChainTracer
from langsmith import Client

from src.tools import create_tools_from_agent_config, CredentialError
from src.utils.pdf_to_images import build_pdf_message
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

if not os.getenv("LANGCHAIN_API_KEY") and os.getenv("LANGSMITH_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")

callbacks = [
    LangChainTracer(
        project_name="dynamic-agent",
        client=Client(
            api_url=os.getenv("LANGSMITH_ENDPOINT"),
            api_key=os.getenv("LANGSMITH_API_KEY")
        )
    )
] if os.getenv("LANGSMITH_API_KEY") else []


def _is_transient_ssl_db_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "ssl connection has been closed unexpectedly" in text
        or "server closed the connection unexpectedly" in text
        or "connection reset by peer" in text
        or "could not receive data from server" in text
    )


def _db_retry_once(db, operation_name: str, fn):
    try:
        return fn()
    except OperationalError as e:
        if not _is_transient_ssl_db_error(e):
            raise
        print(f"[AGENT COMPLETION] Transient DB SSL error during {operation_name}; retrying once...")
        try:
            db.rollback()
        except Exception:
            pass
        # Close the session to release the broken connection back to the
        # pool (QueuePool) or discard it (NullPool).  The next query
        # auto-acquires a fresh connection through the engine.
        db.close()
        time.sleep(0.5)  # brief backoff so the pooler can recover
        return fn()


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
    try:
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']

        agent = _db_retry_once(
            db,
            "load agent",
            lambda: db.query(Agent).filter(Agent.id == agent_id).first(),
        )

        if not agent or not can_access_agent(db, account_id, agent_id):
            yield sse_error("Agent not found", "The specified agent was not found or you do not have access.")
            return

        if not agent.config:
            print(f"[AGENT COMPLETION] Agent {agent_id} has no config")
            yield sse_error("Invalid agent configuration", "Agent configuration is missing.")
            return

        config_data = agent.config.get('data', {})
        config_version = agent.config.get('version', 1)
        system_prompt_raw = config_data.get('systemPrompt', 'You are a helpful assistant.')
        var_context = build_variable_context(agent_name=agent.name)
        system_prompt_resolved = resolve_template_variables(system_prompt_raw, var_context)
        system_prompt = system_prompt_resolved.replace("{", "{{").replace("}", "}}")
        tool_count = len(config_data.get('knowledgeBases' if config_version == 1 else 'tools', []))
        print(f"[AGENT COMPLETION] Config v{config_version} - system_prompt length: {len(system_prompt)}, tools: {tool_count}")

        model_config = get_model_config(agent.config)
        provider = model_config['provider']
        model_name = model_config['model']
        print(f"[AGENT COMPLETION] Using model: {provider}/{model_name}")

        required_credential_type = get_required_credential_type(provider)
        credentials = {}

        if required_credential_type:
            credential = _db_retry_once(
                db,
                "load provider credential",
                lambda: db.query(Credential).filter(
                    Credential.account_id == account_id,
                    Credential.service_name == required_credential_type
                ).first(),
            )

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

        try:
            session_uuid = uuid.UUID(session_id)
        except ValueError:
            yield sse_error("Invalid sessionId format", "The sessionId must be a valid UUID format.")
            return

        session = _db_retry_once(
            db,
            "load chat session",
            lambda: db.query(ChatSession).filter(
                ChatSession.session_id == session_uuid,
                ChatSession.account_id == account_id
            ).first(),
        )

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

        db_messages = _db_retry_once(
            db,
            "load chat messages",
            lambda: db.query(ChatMessage).filter(
                ChatMessage.chat_session_id == session.id
            ).order_by(ChatMessage.created_at.asc()).all(),
        )

        message_history = build_message_history(db_messages)
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

        if tools:
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
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ])
            agent_langchain = None

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

        # ── Release the DB connection ──────────────────────────────
        # All reads are done.  Close the session so the underlying
        # connection returns to the pool (QueuePool) or is discarded
        # (NullPool) *before* the long-running LLM stream begins.
        # The streaming helpers use short-lived sessions for writes.
        chat_session_id = session.id  # grab PK before detaching
        db.close()
        print("[AGENT COMPLETION] DB connection released before streaming")
        # ───────────────────────────────────────────────────────────

        user_message_stored = False
        tool_calls = []

        if agent_executor:
            async for event_data in _stream_agent_executor(
                agent_executor=agent_executor,
                agent_input=agent_input,
                prompt=prompt,
                pdf_filename=pdf_filename,
                chat_session_id=chat_session_id,
                tool_calls=tool_calls,
                user_message_stored=user_message_stored
            ):
                yield event_data
        else:
            async for event_data in _stream_simple_chat(
                llm=llm,
                prompt_template=prompt_template,
                message_history=message_history,
                agent_input=agent_input,
                prompt=prompt,
                pdf_filename=pdf_filename,
                chat_session_id=chat_session_id,
                callbacks=callbacks
            ):
                yield event_data

    except Exception as e:
        print(f"[AGENT COMPLETION] Fatal error in generator: {e}")
        import traceback
        traceback.print_exc()
        yield sse_error("Internal server error", str(e))


def _store_user_msg(chat_session_id: int, prompt: str, pdf_filename: Optional[str]):
    """Write user message using a short-lived DB session."""
    db = SessionLocal()
    try:
        store_user_message(db, chat_session_id, prompt, pdf_filename)
    finally:
        db.close()


def _store_ai_msg(chat_session_id: int, content: str, tool_calls=None):
    """Write AI message using a short-lived DB session."""
    db = SessionLocal()
    try:
        store_ai_message(db, chat_session_id, content, tool_calls)
    finally:
        db.close()


async def _stream_agent_executor(
    agent_executor,
    agent_input,
    prompt: str,
    pdf_filename: Optional[str],
    chat_session_id: int,
    tool_calls: list,
    user_message_stored: bool
):
    print(f"[AGENT COMPLETION] Streaming events from agent executor")
    print(f"[AGENT COMPLETION] Prompt: {prompt[:100]}...")

    async for event in agent_executor.astream_events(
        {"input": agent_input},
        version="v1",
    ):
        kind = event["event"]

        if kind == "on_chain_start":
            if event["name"] == "Agent":
                yield sse_event("on_chain_start")

        elif kind == "on_chain_end":
            if event["name"] == "Agent":
                content = event['data'].get('output', {}).get('output', '')
                if content:
                    _store_ai_msg(chat_session_id, content, tool_calls if tool_calls else None)
                    yield sse_event("on_chain_end", data=content, tool_calls=tool_calls)

        elif kind == "on_chat_model_start":
            if not user_message_stored:
                _store_user_msg(chat_session_id, prompt, pdf_filename)
                user_message_stored = True
            yield sse_event("on_chat_model_start", tool_calls=tool_calls)

        elif kind == "on_chat_model_stream":
            content = event["data"]["chunk"].content
            if content:
                yield sse_event("on_chat_model_stream", data=content)

        elif kind == "on_tool_start":
            yield sse_event("on_tool_start", data=f"Starting tool: {event['name']} with inputs: {event['data'].get('input')}")

        elif kind == "on_tool_end":
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
    chat_session_id: int,
    callbacks: list
):
    print(f"[AGENT COMPLETION] Using simple chat mode (no tools)")
    _store_user_msg(chat_session_id, prompt, pdf_filename)
    yield sse_event("on_chat_model_start")
    full_response = ""
    chunk_count = 0

    try:
        if isinstance(agent_input, str):
            formatted_input = prompt_template.format_messages(
                chat_history=message_history.messages,
                input=agent_input
            )
        else:
            messages = [
                ("system", prompt_template.messages[0].prompt.template),
            ]
            for msg in message_history.messages:
                messages.append(msg)
            messages.append(agent_input)
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

    if full_response:
        _store_ai_msg(chat_session_id, full_response)
    yield sse_event("on_chain_end", data=full_response)


@router.post("/{agent_id}/completion")
@limiter.limit("200/minute")
async def agent_completion(
    agent_id: int,
    request_body: ChatSessionPrompt,
    db: db_dependency,
    auth: auth_dependency,
    request: Request
):
    """
    Stream completion from a dynamically configured agent.
    Same contract as main AI API completion endpoint.
    """
    print(f"[AGENT COMPLETION] Received request for agent_id: {agent_id}")
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
