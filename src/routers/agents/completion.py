"""
Agent completion endpoint - dynamically configures agents based on agent config.
"""
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid
import json
import os
import aiohttp
from fastapi import APIRouter, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from src.deps import db_dependency, auth_dependency
from src.db.models import Agent, Account, ChatAppSession, ChatAppMessage, Credential
from src.db.service_name import ServiceName
from src.routers.credentials.encryption import decrypt_api_key
from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt
from src.core.clients import pc
from slowapi import Limiter
from slowapi.util import get_remote_address
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_classic import hub
from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.tools import StructuredTool
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tracers import LangChainTracer
from langsmith import Client
from pydantic import BaseModel, Field

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

load_dotenv()

# Set LANGCHAIN_API_KEY from LANGSMITH_API_KEY if not already set
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


async def create_retrieval_tool_for_kb(
    knowledge_base: Dict[str, Any],
    account_id: int,
    db
) -> Optional[StructuredTool]:
    """
    Create a retrieval tool for a knowledge base.
    
    Args:
        knowledge_base: Dict with 'provider', 'index', 'namespace', optionally 'description'
        account_id: Account ID for fetching credentials
        db: Database session
    
    Returns:
        StructuredTool for retrieval, or None if provider not supported
    """
    provider = knowledge_base.get('provider', '').lower()
    index_name = knowledge_base.get('index')
    namespace = knowledge_base.get('namespace')
    description = knowledge_base.get('description', f"Search the {namespace} knowledge base")
    
    if provider != 'pinecone':
        print(f"Unsupported provider: {provider}")
        return None
    
    # Get Pinecone API key from credentials
    credential = db.query(Credential).filter(
        Credential.account_id == account_id,
        Credential.service_name == ServiceName.PINECONE_API_KEY
    ).first()
    
    if not credential:
        print(f"No Pinecone API key found for account {account_id}")
        return None
    
    try:
        pinecone_api_key = decrypt_api_key(credential.encrypted_api_key)
    except Exception as e:
        print(f"Failed to decrypt Pinecone API key: {e}")
        return None
    
    # Create Pinecone client for this specific index
    from pinecone import Pinecone
    pc_client = Pinecone(api_key=pinecone_api_key)
    index = pc_client.Index(index_name)
    
    async def retrieval_impl(query: str, top_k: int = 10) -> Dict:
        """Retrieve relevant documents from the knowledge base."""
        try:
            # Get embedding for the query
            embedding = {}
            async with aiohttp.ClientSession() as session:
                url = f"{os.getenv('EMBEDDINGS_API_URL')}/huggingface/embedding"
                payload = {"input": query}
                
                try:
                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            raise aiohttp.ClientError(f"Request failed with status code {response.status}: {await response.text()}")
                        result = await response.json()
                        embedding = result['embedding']
                except aiohttp.ClientError as e:
                    print(f"Error occurred during API request: {e}")
                    return {"error": f"Failed to generate embedding: {str(e)}"}
            
            # Query Pinecone
            results = index.query(
                vector=embedding,
                top_k=top_k,
                include_values=False,
                include_metadata=True,
                namespace=namespace
            )
            
            if not results['matches']:
                return {"results": [], "message": "No relevant documents found"}
            
            # Format results
            formatted_results = []
            for match in results['matches']:
                formatted_results.append({
                    'metadata': match.get('metadata', {}),
                    'score': match.get('score', 0.0),
                    'id': match.get('id')
                })
            
            return {
                "results": formatted_results,
                "namespace": namespace,
                "index": index_name
            }
        except Exception as e:
            print(f"Error in retrieval: {e}")
            return {"error": str(e)}
    
    class SearchQuery(BaseModel):
        query: str = Field(description="The search query to find relevant documents")
        top_k: int = Field(default=10, description="Number of results to return")
    
    return StructuredTool.from_function(
        func=retrieval_impl,
        name=f"search_{namespace}",
        description=description,
        args_schema=SearchQuery
    )


async def generator(
    agent_id: int,
    sessionId: str,
    prompt: str,
    db,
    auth: dict
):
    """
    Generator function for streaming agent completion.
    Dynamically configures agent based on agent config from database.
    """
    try:
        print(f"[AGENT COMPLETION] Starting completion for agent_id={agent_id}, sessionId={sessionId}")
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        
        # Get agent and verify ownership
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id
        ).first()
        
        if not agent:
            print(f"[AGENT COMPLETION] Agent {agent_id} not found for account {account_id}")
            yield json.dumps({
                "event": "error",
                "data": {
                    "error": "Agent not found",
                    "message": "The specified agent was not found or does not belong to you."
                }
            }, separators=(',', ':'))
            return
        
        # Extract config
        if not agent.config:
            print(f"[AGENT COMPLETION] Agent {agent_id} has no config")
            yield json.dumps({
                "event": "error",
                "data": {
                    "error": "Invalid agent configuration",
                    "message": "Agent configuration is missing."
                }
            }, separators=(',', ':'))
            return
        
        config_data = agent.config.get('data', {})
        system_prompt = config_data.get('systemPrompt', 'You are a helpful assistant.')
        knowledge_bases = config_data.get('knowledgeBases', [])
        print(f"[AGENT COMPLETION] Config extracted - system_prompt length: {len(system_prompt)}, knowledge_bases: {len(knowledge_bases)}")
        
        # Get OpenAI API key
        credential = db.query(Credential).filter(
            Credential.account_id == account_id,
            Credential.service_name == ServiceName.OPENAI_API_KEY
        ).first()
        
        if not credential:
            yield json.dumps({
                "event": "error",
                "data": {
                    "error": "OpenAI API key required",
                    "message": "Please add your OpenAI API key in your account settings."
                }
            }, separators=(',', ':'))
            return
        
        try:
            openai_api_key = decrypt_api_key(credential.encrypted_api_key)
        except Exception as e:
            yield json.dumps({
                "event": "error",
                "data": {
                    "error": "Failed to retrieve API key",
                    "message": str(e)
                }
            }, separators=(',', ':'))
            return
        
        # Initialize LLM
        llm = ChatOpenAI(
            temperature=0,
            streaming=True,
            api_key=openai_api_key,
            stream_usage=True,
            model="gpt-4o-mini",
        )
        
        # Get session and messages
        try:
            session_uuid = uuid.UUID(sessionId)
            session = db.query(ChatAppSession).filter(
                ChatAppSession.session_id == session_uuid,
                ChatAppSession.account_id == account_id
            ).first()
            
            if not session:
                yield json.dumps({
                    "event": "error",
                    "data": {
                        "error": "Session not found",
                        "message": "The specified session was not found or does not belong to you."
                    }
                }, separators=(',', ':'))
                return
            
            db_messages = db.query(ChatAppMessage).filter(
                ChatAppMessage.chat_app_session_id == session.id
            ).order_by(ChatAppMessage.created_at.asc()).all()
            
        except ValueError:
            yield json.dumps({
                "event": "error",
                "data": {
                    "error": "Invalid sessionId format",
                    "message": "The sessionId must be a valid UUID format."
                }
            }, separators=(',', ':'))
            return
        
        # Build message history
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
        
        # Create retrieval tools from knowledge bases
        tools = []
        retrieval_calls = []
        
        for kb in knowledge_bases:
            tool = await create_retrieval_tool_for_kb(kb, account_id, db)
            if tool:
                tools.append(tool)
                retrieval_calls.append({
                    "namespace": kb.get('namespace'),
                    "index": kb.get('index')
                })
        
        print(f"[AGENT COMPLETION] Created {len(tools)} tools, using {'agent executor' if tools else 'simple chat'} mode")
        
        # Create agent with system prompt
        if tools:
            # Agent with tools (RAG agent)
            prompt_template = hub.pull("hwchase17/openai-tools-agent")
            # Bind tools to LLM (required for tool calling)
            llm_with_tools = llm.bind_tools(tools)
            agent_langchain = create_openai_tools_agent(
                llm_with_tools.with_config({"tags": ["agent_llm"]}),
                tools,
                prompt_template
            )
            print(f"[AGENT COMPLETION] Agent created with {len(tools)} tools bound to LLM")
        else:
            # Simple chat agent without tools - we'll handle this in the streaming loop
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}")
            ])
            agent_langchain = None  # Will use prompt_template directly
        
        # Create memory
        memory = ConversationBufferMemory(
            memory_key="chat_history" if tools else None,
            chat_memory=message_history,
            return_messages=True,
            output_key="output" if tools else None
        )
        
        # Create agent executor
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
                    "agent_id": agent_id
                },
                "tags": [f"user:{user_email}", f"agent:{agent_id}"]
            })
            print(f"[AGENT COMPLETION] Agent EXECUTOR created with {len(tools)} tools, callbacks: {len(callbacks) if callbacks else 0}")
        else:
            # For simple chat without tools, we'll use the prompt template directly
            agent_executor = None
        
        # Track if user message is stored
        user_message_stored = False
        
        # Stream events - matching kalygoAgent structure exactly
        if agent_executor:
            print(f"[AGENT COMPLETION] Streaming events from agent executor")
            print(f"[AGENT COMPLETION] Agent executor type: {type(agent_executor)}")
            print(f"[AGENT COMPLETION] Prompt: {prompt}")
            
            # Direct async for loop - matching kalygoAgent exactly
            async for event in agent_executor.astream_events(
                {
                    "input": prompt
                },
                version="v1",
            ):
                kind = event["event"]
                print(f"[AGENT COMPLETION] Event: {kind}", flush=True)
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
                        print(content, end="|", flush=True)
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
                    # print(f"Tool output was: {event['data'].get('output')}")
                    print("--")
                    
                    # Track retrieval calls if it's a retrieval tool
                    tool_name = event['name']
                    if any(tool_name.startswith(f"search_{kb.get('namespace', '')}") for kb in knowledge_bases):
                        tool_input = event['data'].get('input', {})
                        tool_output = event['data'].get('output', {})
                        
                        # Extract query from tool input
                        query = tool_input.get('query', 'Unknown query')
                        
                        # Extract results from tool output
                        results = tool_output.get('results', [])
                        
                        # Format results for response
                        formatted_results = []
                        for result in results:
                            formatted_results.append({
                                "chunk_id": result.get("id", "N/A"),
                                "score": result.get("score", 0.0),
                                "content": result.get("metadata", {}).get("content", ""),
                                "metadata": result.get("metadata", {})
                            })
                        
                        retrieval_calls.append({
                            "query": query,
                            "results": formatted_results,
                            "namespace": tool_output.get('namespace', ''),
                            "index": tool_output.get('index', '')
                        })
                    
                    yield json.dumps({
                        "event": "on_tool_end",
                    }, separators=(',', ':'))
        else:
            # Simple chat without tools - use prompt template with streaming
            print(f"[AGENT COMPLETION] Using simple chat mode (no tools)")
            if not user_message_stored:
                try:
                    user_message = ChatAppMessage(
                        message={"role": "human", "content": prompt},
                        chat_app_session_id=session.id
                    )
                    db.add(user_message)
                    db.commit()
                    user_message_stored = True
                    print(f"[AGENT COMPLETION] Stored user message")
                except Exception as e:
                    print(f"Failed to store user message: {e}")
                    db.rollback()
            
            yield json.dumps({
                "event": "on_chat_model_start",
            }, separators=(',', ':'))
            
            # Use prompt template to format messages properly
            print(f"[AGENT COMPLETION] Streaming with prompt template, history has {len(message_history.messages)} messages")
            
            # Stream response using the prompt template
            full_response = ""
            chunk_count = 0
            try:
                # Use astream_events for consistent event handling
                async for event in llm.astream_events(
                    prompt_template.format_messages(
                        chat_history=message_history.messages,
                        input=prompt
                    ),
                    version="v1"
                ):
                    kind = event["event"]
                    
                    if kind == "on_chat_model_stream":
                        print(f"[AGENT COMPLETION] on_chat_model_stream")
                        content = event["data"]["chunk"].content
                        if content:
                            chunk_count += 1
                            full_response += content
                            print(f"[AGENT COMPLETION] Chunk {chunk_count}: {content[:50]}...")
                            yield json.dumps({
                                "event": "on_chat_model_stream",
                                "data": content
                            }, separators=(',', ':'))
                
                print(f"[AGENT COMPLETION] Finished streaming - {chunk_count} chunks, total length: {len(full_response)}")
            except Exception as e:
                print(f"[AGENT COMPLETION] Error during streaming: {e}")
                import traceback
                traceback.print_exc()
                yield json.dumps({
                    "event": "error",
                    "data": {
                        "error": "Streaming error",
                        "message": str(e)
                    }
                }, separators=(',', ':'))
                return
            
            # Store AI response
            if full_response:
                try:
                    ai_message = ChatAppMessage(
                        message={"role": "ai", "content": full_response},
                        chat_app_session_id=session.id
                    )
                    db.add(ai_message)
                    db.commit()
                    print(f"[AGENT COMPLETION] Stored AI response")
                except Exception as e:
                    print(f"Failed to store AI response: {e}")
                    db.rollback()
            
            yield json.dumps({
                "event": "on_chain_end",
                "data": full_response
            }, separators=(',', ':'))
            
    except Exception as e:
        print(f"[AGENT COMPLETION] Fatal error in generator: {e}")
        import traceback
        traceback.print_exc()
        yield json.dumps({
            "event": "error",
            "data": {
                "error": "Internal server error",
                "message": str(e)
            }
        }, separators=(',', ':'))


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
    """
    return StreamingResponse(
        generator(
            agent_id=agent_id,
            sessionId=request_body.sessionId,
            prompt=request_body.prompt,
            db=db,
            auth=auth
        ),
        media_type='text/event-stream'
    )
