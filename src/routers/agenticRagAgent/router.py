from typing import List
from fastapi import APIRouter, Request

from .tools import gptuesday_tool, tad_tool, retrieval_with_reranking_tool
from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt

from slowapi import Limiter
from slowapi.util import get_remote_address

import json
import os
import psycopg

from fastapi.responses import StreamingResponse

from langchain.callbacks import LangChainTracer
from langsmith import Client

from langchain import hub
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_openai import ChatOpenAI
from langchain_postgres import PostgresChatMessageHistory
from langchain.memory import ConversationBufferMemory

from src.deps import jwt_dependency

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv

load_dotenv()

callbacks = [
  LangChainTracer(
    project_name="agentic-rag-agent",
    client=Client(
      api_url=os.getenv("LANGSMITH_ENDPOINT"),
      api_key=os.getenv("LANGSMITH_API_KEY")
    )
  )
]

router = APIRouter()

async def generator(sessionId: str, prompt: str):
    llm = ChatOpenAI(temperature=0, streaming=True, model="gpt-4o-mini")

    # Get the prompt to use - you can modify this!
    prompt_template = hub.pull("hwchase17/openai-tools-agent")
    # tools = [serp_tool, gptuesday_tool]
    # tools = [gptuesday_tool, tad_tool, retrieval_with_reranking_tool]
    tools = [retrieval_with_reranking_tool]
    
    agent = create_openai_tools_agent(
        llm.with_config({"tags": ["agent_llm"]}), tools, prompt_template
    )
    
    # Track retrieval calls
    retrieval_calls = []
    
    conn_info = os.getenv("POSTGRES_URL")
    sync_connection = psycopg.connect(conn_info)

    print('sessionId', sessionId)

    message_history = PostgresChatMessageHistory(
        'chat_history', # table name
        sessionId,
        sync_connection=sync_connection
    )
    
    memory = ConversationBufferMemory(
        memory_key="chat_history", chat_memory=message_history, return_messages=True, output_key="output"
    )

    agent_executor = AgentExecutor(agent=agent, tools=tools, memory=memory).with_config(
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
                    print(content, end="|")
                    yield json.dumps({
                        "event": "on_chain_end",
                        "data": content,
                        "retrieval_calls": retrieval_calls
                    }, separators=(',', ':'))
        if kind == "on_chat_model_start":
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
            if event['name'] == "retrieval_with_reranking":
                tool_input = event['data'].get('input', {})
                tool_output = event['data'].get('output', {})
                
                # Extract query from tool input
                query = tool_input.get('query', 'Unknown query')
                
                # Extract results from tool output
                reranked_results = tool_output.get('reranked_results', [])
                similarity_results = tool_output.get('similarity_results', [])
                
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
                    "similarity_results": similarity_results,
                    "message": tool_output.get('message', ''),
                    "namespace": tool_output.get('namespace', '')
                })
            
            yield json.dumps({
                "event": "on_tool_end",
            }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: ChatSessionPrompt, jwt: jwt_dependency, request: Request):
    return StreamingResponse(generator(prompt.sessionId, prompt.content), media_type='text/event-stream')