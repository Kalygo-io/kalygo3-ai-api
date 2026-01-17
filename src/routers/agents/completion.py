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
        account_id = int(auth['id']) if isinstance(auth['id'], str) else auth['id']
        
        # Get agent and verify ownership
        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.account_id == account_id
        ).first()
        
        if not agent:
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
        
        # Create agent with system prompt
        if tools:
            # Agent with tools (RAG agent)
            prompt_template = hub.pull("hwchase17/openai-tools-agent")
            agent_langchain = create_openai_tools_agent(
                llm.with_config({"tags": ["agent_llm"]}),
                tools,
                prompt_template
            )
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
        else:
            # For simple chat without tools, we'll use the prompt template directly
            agent_executor = None
        
        # Track if user message is stored
        user_message_stored = False
        
        # Stream events
        if agent_executor:
            async for event in agent_executor.astream_events(
                {"input": prompt},
                version="v1",
            ):
                kind = event["event"]
                
                if kind == "on_chain_start":
                    if event["name"] == "Agent":
                        yield json.dumps({
                            "event": "on_chain_start",
                        }, separators=(',', ':'))
                
                elif kind == "on_chain_end":
                    if event["name"] == "Agent":
                        content = event['data'].get('output', {}).get('output', '')
                        if content:
                            try:
                                ai_message = ChatAppMessage(
                                    message={"role": "ai", "content": content},
                                    chat_app_session_id=session.id
                                )
                                db.add(ai_message)
                                db.commit()
                            except Exception as e:
                                print(f"Failed to store AI response: {e}")
                                db.rollback()
                            
                            yield json.dumps({
                                "event": "on_chain_end",
                                "data": content,
                                "retrieval_calls": retrieval_calls
                            }, separators=(',', ':'))
                
                if kind == "on_chat_model_start":
                    if not user_message_stored:
                        try:
                            user_message = ChatAppMessage(
                                message={"role": "human", "content": prompt},
                                chat_app_session_id=session.id
                            )
                            db.add(user_message)
                            db.commit()
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
                        yield json.dumps({
                            "event": "on_chat_model_stream",
                            "data": content
                        }, separators=(',', ':'))
                
                elif kind == "on_tool_start":
                    yield json.dumps({
                        "event": "on_tool_start",
                    }, separators=(',', ':'))
                
                elif kind == "on_tool_end":
                    yield json.dumps({
                        "event": "on_tool_end",
                    }, separators=(',', ':'))
        else:
            # Simple chat without tools - use prompt template with streaming
            if not user_message_stored:
                try:
                    user_message = ChatAppMessage(
                        message={"role": "human", "content": prompt},
                        chat_app_session_id=session.id
                    )
                    db.add(user_message)
                    db.commit()
                    user_message_stored = True
                except Exception as e:
                    print(f"Failed to store user message: {e}")
                    db.rollback()
            
            yield json.dumps({
                "event": "on_chat_model_start",
            }, separators=(',', ':'))
            
            # Format messages with system prompt and history
            messages = [SystemMessage(content=system_prompt)]
            messages.extend(message_history.messages)
            messages.append(HumanMessage(content=prompt))
            
            # Stream response
            full_response = ""
            async for chunk in llm.astream(messages):
                content = chunk.content
                if content:
                    full_response += content
                    yield json.dumps({
                        "event": "on_chat_model_stream",
                        "data": content
                    }, separators=(',', ':'))
            
            # Store AI response
            if full_response:
                try:
                    ai_message = ChatAppMessage(
                        message={"role": "ai", "content": full_response},
                        chat_app_session_id=session.id
                    )
                    db.add(ai_message)
                    db.commit()
                except Exception as e:
                    print(f"Failed to store AI response: {e}")
                    db.rollback()
            
            yield json.dumps({
                "event": "on_chain_end",
                "data": full_response
            }, separators=(',', ':'))
            
    except Exception as e:
        print(f"Error in generator: {e}")
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
