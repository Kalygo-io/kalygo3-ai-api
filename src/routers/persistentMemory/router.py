from typing import List
from fastapi import APIRouter, Request
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_postgres import PostgresChatMessageHistory

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.schemas.ChatSessionPromptV2 import ChatSessionPromptV2

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
      api_url=os.getenv("LANGSMITH_ENDPOINT"),
      api_key=os.getenv("LANGSMITH_API_KEY")
    )
  )
]

router = APIRouter()

async def generator(chatSessionPrompt: ChatSessionPromptV2):
    
    # model: str = "gpt-4o-mini"
    # llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"))
    model: str = "claude-3-5-sonnet-20240620"
    llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)

    print('chatSessionPrompt.sessionId', chatSessionPrompt.sessionId)

    # conn_info = os.getenv("POSTGRES_URL")
    # with psycopg.connect(conn_info) as sync_connection:
        # history = PostgresChatMessageHistory(
        #     'chat_history', # table name
        #     sessionId,
        #     sync_connection=sync_connection
        # )

    print("DEBUGGING MESSAGE LIST")
    for message in chatSessionPrompt.chatHistory:
        print(message)
    print("DEBUGGING MESSAGE LIST END")

    system_message = [("human", "You're an assistant. Bold key terms in your responses.")]
    chat_history_messages = [(msg.role, msg.content) for msg in chatSessionPrompt.chatHistory]
    all_messages = system_message + chat_history_messages + [("human", chatSessionPrompt.prompt)]
    
    async for evt in llm.astream_events(all_messages, version="v1", config={"callbacks": callbacks}, model=model):
        if evt["event"] == "on_chat_model_start":
            yield json.dumps({
                "event": "on_chat_model_start"
            }, separators=(',', ':'))

        elif evt["event"] == "on_chat_model_stream":
            yield json.dumps({
                "event": "on_chat_model_stream",
                "data": evt["data"]['chunk'].content
            }, separators=(',', ':'))

        elif evt["event"] == "on_chat_model_end":
            yield json.dumps({
                "event": "on_chat_model_end",
                "data": evt["data"]['output'].content
            }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(chatSessionPrompt: ChatSessionPromptV2, jwt: jwt_dependency, request: Request):
    return StreamingResponse(generator(chatSessionPrompt), media_type='text/event-stream')