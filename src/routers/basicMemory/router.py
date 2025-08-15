from fastapi import APIRouter, Request
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_postgres import PostgresChatMessageHistory

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.schemas.ChatSessionPrompt import ChatSessionPrompt

import json
import os

from fastapi.responses import StreamingResponse

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.callbacks import LangChainTracer
from langsmith import Client
import psycopg
from src.deps import jwt_dependency

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv

load_dotenv()

callbacks = [
  LangChainTracer(
    project_name="basic-memory",
    client=Client(
      api_url=os.getenv("LANGCHAIN_ENDPOINT"),
      api_key=os.getenv("LANGCHAIN_API_KEY")
    )
  )
]

router = APIRouter()

async def generator(sessionId: str, prompt: str):
    
    # model: str = "gpt-4o-mini"
    # llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"))
    model: str = "claude-3-5-sonnet-20240620"
    llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)

    conn_info = os.getenv("POSTGRES_URL")
    with psycopg.connect(conn_info) as sync_connection:

        history = PostgresChatMessageHistory(
            'chat_history', # table name
            sessionId,
            sync_connection=sync_connection
        )

        promptTemplate = ChatPromptTemplate.from_messages(
            [
                ("system", "You're an assistant. Bold key terms in your responses."),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{input}"),
            ]
        )

        messages = promptTemplate.format_messages(input=prompt, history=history.messages)

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

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: ChatSessionPrompt, jwt: jwt_dependency, request: Request):
    return StreamingResponse(generator(prompt.sessionId, prompt.content), media_type='text/event-stream')