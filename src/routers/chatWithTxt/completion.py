from fastapi import APIRouter, Request
from langchain_anthropic import ChatAnthropic
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
        model: str = "claude-3-5-sonnet-20240620"
        llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)

        conn_info = os.getenv("POSTGRES_URL")
        with psycopg.connect(conn_info) as sync_connection:

            history = PostgresChatMessageHistory(
                'chat_history', # table name
                sessionId,
                sync_connection=sync_connection
            )

            embedding = await fetch_embedding(jwt, prompt) # fetch embedding from embedding service

            index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))

            results = index.query(
                vector=embedding,
                top_k=10,
                include_values=False,
                include_metadata=True,
                namespace='chat_with_txt'
            )

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
                "query": prompt,
                "documents": docs,
                "top_n": min(5, len(docs))
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
                reranked_matches.append({
                    "metadata": metadata,
                    "relevance_score": relevance_score,
                    "similarity_score": similarity_score
                })

            print('4')

            for match in reranked_matches:
                relevance_score = match["relevance_score"]
                similarity_score = match["similarity_score"]
                chunk_id = match["metadata"].get("chunk_id", "N/A")
                content = match["metadata"].get("content", "")
                print(f"Relevance Score: {relevance_score}, Similarity Score: {similarity_score}, Chunk ID: {chunk_id}, Content: {content[:10]}")

            print('4.5')

            promptTemplate = ChatPromptTemplate.from_messages(
                [
                    ("system", f"You're a helpful assistant. If information is not provided in the knowledge base regarding the prompt then do NOT fabricate an answer. Bold key terms in your responses. FYI today is {datetime.now().strftime('%Y-%m-%d')}"),
                    MessagesPlaceholder(variable_name="history"),
                    ("human", "{input}"),
                ]
            )

            prompt_with_relevant_knowledge = "# RELEVANT KNOWLEDGE\n\n" + "\n".join([f"--------\nRelevance Score: {r['relevance_score']}, Similarity Score: {r['similarity_score']}\nChunk: {r['metadata']['chunk_id']} of {r['metadata']['total_chunks']}--------\n\n{r['metadata']['content']}\n" for r in reranked_matches]) + "\n\n" + "# PROMPT\n\n" + prompt
            messages = promptTemplate.format_messages(input=prompt_with_relevant_knowledge, history=history.messages)

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
                            "content": match["metadata"].get("content", "")
                        })

                    yield json.dumps({
                        "event": "on_chat_model_start",
                        "reranked_chunks": matches_data
                    }, separators=(',', ':'))

                elif evt["event"] == "on_chat_model_stream":
                    yield json.dumps({
                        "event": "on_chat_model_stream",
                        "data": evt["data"]['chunk'].content
                    }, separators=(',', ':'))

                elif evt["event"] == "on_chat_model_end":
                    history.add_ai_message(evt['data']['output'].content)

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