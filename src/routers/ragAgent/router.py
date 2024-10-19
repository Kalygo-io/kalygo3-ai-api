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

# from src.clients.psycopg_client import sync_connection

from dotenv import load_dotenv
from src.services import fetch_embedding
from src.deps import jwt_dependency
from datetime import datetime
import psycopg

limiter = Limiter(key_func=get_remote_address)

load_dotenv()

callbacks = [
  LangChainTracer(
    project_name="rag-agent",
    client=Client(
      api_url=os.getenv("LANGCHAIN_ENDPOINT"),
      api_key=os.getenv("LANGCHAIN_API_KEY")
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
                top_k=3,
                include_values=False,
                include_metadata=True,
                namespace='aisalon_miami'
            )

            promptTemplate = ChatPromptTemplate.from_messages(
                [
                    ("system", f"You're a helpful assistant who reports fact-based information related to the AiSalon Miami community. If information is not provided in the knowledge base regarding the prompt then do NOT fabricate an answer. Bold key terms in your responses. FYI today is {datetime.now().strftime('%Y-%m-%d')}"),
                    MessagesPlaceholder(variable_name="history"),
                    ("human", "{input}"),
                ]
            )

            prompt_with_relevant_knowledge = "# RELEVANT KNOWLEDGE\n\n" + "\n".join([f"Q: {r['metadata']['q']}\nA: {r['metadata']['a']}" for r in results['matches']]) + "\n\n" + "# PROMPT\n\n" + prompt
            messages = promptTemplate.format_messages(input=prompt_with_relevant_knowledge, history=history.messages)

            async for evt in llm.astream_events(messages, version="v1", config={"callbacks": callbacks}, model=model):
                if evt["event"] == "on_chat_model_start":
                    history.add_user_message(prompt)

                    yield json.dumps({
                        "event": "on_chat_model_start"
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
            "event": "error",
            "message": str(e)
        }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: ChatSessionPrompt, decoded_jwt: jwt_dependency, request: Request):

    jwt = request.cookies.get("jwt")

    return StreamingResponse(generator(jwt, prompt.sessionId, prompt.content), media_type='text/event-stream')