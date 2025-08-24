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
    print(f"DEBUG: Session ID: {sessionId}")
    print(f"DEBUG: Original prompt: {prompt}")

    try:
        #model: str = "claude-3-5-sonnet-20240620"
        #llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)
        
        model: str = "gpt-5"
        llm = ChatOpenAI(model_name=model, temperature=0.2, max_completion_tokens=1024)
        print(f"DEBUG: Using model: {model}")
        
        print("DEBUG: Fetching embedding for prompt...")
        embedding = await fetch_embedding(jwt, prompt) # fetch embedding from embedding service
        print(f"DEBUG: Embedding fetched, vector length: {len(embedding)}")

        index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))
        print(f"DEBUG: Pinecone index initialized: {os.getenv('PINECONE_ALL_MINILM_L6_V2_INDEX')}")

        print("DEBUG: Performing Pinecone similarity search...")
        results = index.query(
            vector=embedding,
            top_k=200,
            include_values=False,
            include_metadata=True,
            namespace='chat_with_txt'
        )

        print(f"DEBUG: Pinecone search completed")
        print(f"DEBUG: Raw Pinecone matches count: {len(results['matches'])}")

        # Check if we have any matches from similarity search
        if not results['matches']:
            print("DEBUG: No Pinecone matches found - skipping reranking")
            # No matches found, skip re-ranking and continue with empty results
            reranked_matches = []
        else:
            print("DEBUG: Pinecone matches found - proceeding to reranking")
            # Prepare documents and query for Cohere Rerank 3.5
            cohere_api_key = os.getenv("COHERE_API_KEY")
            if not cohere_api_key:
                print("DEBUG: ERROR - COHERE_API_KEY not set")
                raise Exception("COHERE_API_KEY not set in environment variables")

            # Gather the documents to rerank
            docs = []
            doc_metadatas = []
            similarity_scores = []
            print(f"DEBUG: Preparing {len(results['matches'])} documents for reranking")
            for i, r in enumerate(results['matches']):
                content = r['metadata'].get('content', '')
                docs.append(content)
                doc_metadatas.append(r['metadata'])
                similarity_scores.append(r['score'])  # Store Pinecone similarity score
                print(f"DEBUG: Document {i+1} - Score: {r['score']:.4f}, Content length: {len(content)} chars")

            # Call Cohere Rerank 3.5 API
            print("DEBUG: Calling Cohere Rerank API...")
            cohere_url = "https://api.cohere.ai/v1/rerank"
            headers = {
                "Authorization": f"Bearer {cohere_api_key}",
                "Content-Type": "application/json"
            }
            rerank_payload = {
                "model": "rerank-v3.5",
                "query": prompt,
                "documents": docs,
                "top_n": min(20, len(docs))
            }
            print(f"DEBUG: Rerank payload - query: '{prompt}', documents: {len(docs)}, top_n: {min(20, len(docs))}")
            
            cohere_response = requests.post(cohere_url, headers=headers, json=rerank_payload)

            if cohere_response.status_code != 200:
                print(f"DEBUG: ERROR - Cohere API returned status {cohere_response.status_code}")
                print(f"DEBUG: Cohere response: {cohere_response.text}")
                raise Exception(f"Cohere Rerank API error: {cohere_response.text}")

            rerank_results = cohere_response.json()
            print(f"DEBUG: Cohere rerank successful, returned {len(rerank_results.get('results', []))} results")

            reranked_matches = []
            for item in rerank_results.get("results", []):
                idx = item["index"]
                relevance_score = item["relevance_score"]
                similarity_score = similarity_scores[idx]  # Get corresponding similarity score
                metadata = doc_metadatas[idx]

                print(f"DEBUG: Rerank result {idx+1} - Relevance: {relevance_score:.4f}, Similarity: {similarity_score:.4f}")

                # Only keep matches with relevance score above 0.2 (20%)
                if relevance_score > 0.1:
                    reranked_matches.append({
                        "metadata": metadata,
                        "relevance_score": relevance_score,
                        "similarity_score": similarity_score
                    })
                    print(f"DEBUG: Added match {idx+1} to final results (relevance: {relevance_score:.4f})")
                else:
                    print(f"DEBUG: Skipped match {idx+1} due to low relevance ({relevance_score:.4f})")

        print(f"DEBUG: Final reranked matches count: {len(reranked_matches)}")

        for match in reranked_matches:
            relevance_score = match["relevance_score"]
            similarity_score = match["similarity_score"]
            content = match["metadata"].get("content", "")
            print(f"DEBUG: Final match - Relevance: {relevance_score:.4f}, Similarity: {similarity_score:.4f}, Content length: {len(content)}")

        if reranked_matches:
            relevant_knowledge = f"""{"\n".join([f"### RERANKED CHUNK {idx + 1} \n\n{match['metadata']['content']}\n" for idx, match in enumerate(reranked_matches)])}"""
            print(f"DEBUG: Knowledge base content prepared with {len(reranked_matches)} chunks")
        else:
            relevant_knowledge = f"""# RELEVANT KNOWLEDGE

No relevant information found in the knowledge base.
"""
            print("DEBUG: No relevant knowledge found - using empty knowledge base")

        # Compose the full prompt
        general_prompt = f"""# TASK

Answer the prompt to the best of your ability given the past history of messages and relevant chunks of knowledge from your external knowledge base

## TOC

[Prompt](##prompt)
[Relevant Knowledge (most relevant to least relevant)] (##relevant-knowledge)

## PROMPT

{prompt}

## RELEVANT KNOWLEDGE (most relevant to least relevant)

{relevant_knowledge.strip()}
"""

        messages = [
            SystemMessage(content=f"You're a helpful assistant. If information is not provided in the knowledge base regarding the prompt then do NOT fabricate an answer. Bold key terms in your responses. FYI today is {datetime.now().strftime('%Y-%m-%d')}"),
            HumanMessage(content=general_prompt)
        ]

        print("DEBUG: Starting LLM streaming...")
        async for evt in llm.astream_events(messages, version="v1", config={"callbacks": callbacks}, model=model):
            if evt["event"] == "on_chat_model_start":
                print("DEBUG: LLM started - adding user message to history")
                # Include re-ranked matches in the response
                matches_data = []
                print(f"DEBUG: Preparing {len(reranked_matches)} reranked matches for client response")
                for i, match in enumerate(reranked_matches):
                    match_data = {
                        "chunk_id": match["metadata"].get("chunk_id", "N/A"),
                        "total_chunks": match["metadata"].get("total_chunks", "N/A"),
                        "relevance_score": match["relevance_score"],
                        "similarity_score": match["similarity_score"],
                        "content": match["metadata"].get("content", ""),
                        "filename": match["metadata"].get("filename", "N/A")
                    }
                    matches_data.append(match_data)
                    print(f"DEBUG: Match {i+1} - Chunk ID: {match_data['chunk_id']}, Relevance: {match_data['relevance_score']:.4f}, Filename: {match_data['filename']}")

                response_data = {
                    "event": "on_chat_model_start",
                    "reranked_chunks": matches_data,
                    "kb_search_query": prompt
                }
                print(f"DEBUG: Sending on_chat_model_start event with {len(matches_data)} chunks")
                yield json.dumps(response_data, separators=(',', ':'))

            elif evt["event"] == "on_chat_model_stream":
                yield json.dumps({
                    "event": "on_chat_model_stream",
                    "data": evt["data"]['chunk'].content
                }, separators=(',', ':'))

            elif evt["event"] == "on_chat_model_end":

                yield json.dumps({
                    "event": "on_chat_model_end"
                }, separators=(',', ':'))
    except Exception as e:
        print(f"DEBUG: ERROR in generator function: {str(e)}")
        print(f"DEBUG: Exception type: {type(e).__name__}")
        import traceback
        print(f"DEBUG: Full traceback: {traceback.format_exc()}")
        # Yield an error event
        yield json.dumps({
            "event": "event_stream_error",
            "data": str(e)
        }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: ChatSessionPrompt, decoded_jwt: jwt_dependency, request: Request):
    print(f"DEBUG: Completion endpoint called")
    print(f"DEBUG: Session ID: {prompt.sessionId}")
    print(f"DEBUG: Content length: {len(prompt.content)}")
    print(f"DEBUG: JWT present: {bool(request.cookies.get('jwt'))}")
    
    jwt = request.cookies.get("jwt")
    return StreamingResponse(generator(jwt, prompt.sessionId, prompt.content), media_type='text/event-stream') 