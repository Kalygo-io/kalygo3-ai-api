from fastapi import APIRouter, Request
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt
from slowapi import Limiter
from slowapi.util import get_remote_address
import json
import os
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_postgres import PostgresChatMessageHistory
from langchain.callbacks import LangChainTracer
from langsmith import Client
from src.core.clients import pc
from dotenv import load_dotenv
from src.services import fetch_embedding
from src.deps import jwt_dependency
from datetime import datetime
import requests
import psycopg
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

limiter = Limiter(key_func=get_remote_address)

load_dotenv()

callbacks = [
    LangChainTracer(
    project_name="chat-with-txt",
    client=Client(
        api_url=os.getenv("LANGSMITH_ENDPOINT"),
        api_key=os.getenv("LANGSMITH_API_KEY"),
    )
    )
]

router = APIRouter()

async def generator(jwt: str, sessionId: str, prompt: str):

    print("---> generator called <---")

    try:
        #model: str = "claude-3-5-sonnet-20240620"
        #llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)
        
        model: str = "gpt-4o-mini"
        llm = ChatOpenAI(model_name=model, temperature=0.2, max_tokens=1024)

        conn_info = os.getenv("POSTGRES_URL")
        with psycopg.connect(conn_info) as sync_connection:

            history = PostgresChatMessageHistory(
                'chat_history', # table name
                sessionId,
                sync_connection=sync_connection
            )

            # Generate a vector search query based on chat history and current prompt
            chat_history_text = ""
            if history.messages:
                # Collect messages in order, but reverse for most recent first
                reversed_messages = list(reversed(history.messages))
                for message in reversed_messages:
                    if hasattr(message, 'type') and message.type == 'human':
                        chat_history_text += f"Human: {message.content}\n"
                    elif hasattr(message, 'type') and message.type == 'ai':
                        chat_history_text += f"Assistant: {message.content}\n"
                    else:
                        if hasattr(message, 'content'):
                            chat_history_text += f"{message.content}\n"

            # Model the search query prompt as below, with the prompt at the top and most recent messages first
            summary_prompt = f"""You are an expert at transforming chat history and user prompts into effective search queries for a knowledge base.

Given the following user prompt and chat history, generate a single, concise search query that best captures the user's current information need. The query should be as specific as possible, using relevant details from both the prompt and the most recent chat messages. Do not include any explanations or extra text—just output the search query.

User Prompt:
{prompt}

Chat History (most recent first):
{chat_history_text}
"""

            # Use the same LLM to generate the search query
            search_query_response = llm.invoke(summary_prompt)
            search_query = search_query_response.content.strip()
            
            print()
            print(f"Generated search query: {search_query}")
            print()

            # Use the generated search query for embedding instead of the original prompt
            embedding = await fetch_embedding(jwt, search_query) # fetch embedding from embedding service

            index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))

            results = index.query(
                vector=embedding,
                top_k=200,
                include_values=False,
                include_metadata=True,
                namespace='chat_with_txt'
            )

            # Check if we have any matches from similarity search
            if not results['matches']:
                # No matches found, skip re-ranking and continue with empty results
                reranked_matches = []
            else:
                # Prepare documents and query for Cohere Rerank 3.5
                cohere_api_key = os.getenv("COHERE_API_KEY")
                if not cohere_api_key:
                    raise Exception("COHERE_API_KEY not set in environment variables")

                # Gather the documents to rerank
                docs = []
                doc_metadatas = []
                similarity_scores = []
                for r in results['matches']:
                    content = r['metadata'].get('content', '')
                    docs.append(content)
                    doc_metadatas.append(r['metadata'])
                    similarity_scores.append(r['score'])  # Store Pinecone similarity score

                # Call Cohere Rerank 3.5 API
                cohere_url = "https://api.cohere.ai/v1/rerank"
                headers = {
                    "Authorization": f"Bearer {cohere_api_key}",
                    "Content-Type": "application/json"
                }
                rerank_payload = {
                    "model": "rerank-v3.5",
                    "query": search_query,
                    "documents": docs,
                    "top_n": min(20, len(docs))
                }
                cohere_response = requests.post(cohere_url, headers=headers, json=rerank_payload)

                if cohere_response.status_code != 200:
                    raise Exception(f"Cohere Rerank API error: {cohere_response.text}")

                rerank_results = cohere_response.json()

                reranked_matches = []
                for item in rerank_results.get("results", []):
                    idx = item["index"]
                    relevance_score = item["relevance_score"]
                    similarity_score = similarity_scores[idx]  # Get corresponding similarity score
                    metadata = doc_metadatas[idx]

                    # Only keep matches with relevance score above 0.2 (20%)
                    if relevance_score > 0.1:
                        reranked_matches.append({
                            "metadata": metadata,
                            "relevance_score": relevance_score,
                            "similarity_score": similarity_score
                        })

            for match in reranked_matches:
                relevance_score = match["relevance_score"]
                similarity_score = match["similarity_score"]
                content = match["metadata"].get("content", "")

            if reranked_matches:
                relevant_knowledge = f"""{"\n".join([f"### RERANKED CHUNK {idx + 1} \n\n{match['metadata']['content']}\n" for idx, match in enumerate(reranked_matches)])}"""
            else:
                relevant_knowledge = f"""# RELEVANT KNOWLEDGE

No relevant information found in the knowledge base.
"""

            # Construct the general prompt as specified

            # Prepare chat history string (most recent to earlier)
            chat_history_str = ""
            for msg in reversed(history.messages):
                if hasattr(msg, "type") and msg.type == "human":
                    chat_history_str += f"HUMAN: {msg.content}\n\n"
                elif hasattr(msg, "type") and msg.type == "ai":
                    chat_history_str += f"AI: {msg.content}\n\n"
                else:
                    # Fallback if type attribute is missing
                    role = getattr(msg, "role", None)
                    if role == "user":
                        chat_history_str += f"HUMAN: {msg.content}\n\n"
                    elif role == "assistant":
                        chat_history_str += f"AI: {msg.content}\n\n"

            # Compose the full prompt
            general_prompt = f"""# TASK

Answer the prompt to the best of your ability given the past history of messages and relevant chunks of knowledge from your external knowledge base

## TOC

[Prompt](##prompt)
[Chat History](##chat-history)
[Relevant Knowledge (most relevant to least relevant)] (##relevant-knowledge)

## PROMPT

{prompt}

## CHAT HISTORY (most recent to earlier)

{chat_history_str.strip()}

## RELEVANT KNOWLEDGE (most relevant to least relevant)

{relevant_knowledge.strip()}
"""

            messages = [
                SystemMessage(content=f"You're a helpful assistant. If information is not provided in the knowledge base regarding the prompt then do NOT fabricate an answer. Bold key terms in your responses. FYI today is {datetime.now().strftime('%Y-%m-%d')}"),
                HumanMessage(content=general_prompt)
            ]

            async for evt in llm.astream_events(messages, version="v1", config={"callbacks": callbacks}, model=model):
                if evt["event"] == "on_chat_model_start":
                    history.add_user_message(prompt)

                    # Include re-ranked matches in the response
                    matches_data = []
                    for match in reranked_matches:
                        matches_data.append({
                            "chunk_id": match["metadata"].get("chunk_id", "N/A"),
                            "total_chunks": match["metadata"].get("total_chunks", "N/A"),
                            "relevance_score": match["relevance_score"],
                            "similarity_score": match["similarity_score"],
                            "content": match["metadata"].get("content", ""),
                            "filename": match["metadata"].get("filename", "N/A")
                        })

                    yield json.dumps({
                        "event": "on_chat_model_start",
                        "reranked_chunks": matches_data,
                        "kb_search_query": search_query
                    }, separators=(',', ':'))

                elif evt["event"] == "on_chat_model_stream":
                    yield json.dumps({
                        "event": "on_chat_model_stream",
                        "data": evt["data"]['chunk'].content
                    }, separators=(',', ':'))

                elif evt["event"] == "on_chat_model_end":

                    if evt['data']['output'].content:
                        history.add_ai_message(evt['data']['output'].content)
                    else:
                        history.add_ai_message("No response from the model")

                    yield json.dumps({
                        "event": "on_chat_model_end"
                    }, separators=(',', ':'))
    except Exception as e:
        # Yield an error event
        yield json.dumps({
            "event": "event_stream_error",
            "data": str(e)
        }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: ChatSessionPrompt, decoded_jwt: jwt_dependency, request: Request):
    jwt = request.cookies.get("jwt")
    return StreamingResponse(generator(jwt, prompt.sessionId, prompt.content), media_type='text/event-stream') 