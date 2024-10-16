from fastapi import APIRouter, Request
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from slowapi import Limiter
from slowapi.util import get_remote_address
from src.core.schemas.Prompt import Prompt
import json
import os
from fastapi.responses import StreamingResponse
from langchain_core.prompts import ChatPromptTemplate
from langchain.callbacks import LangChainTracer
from langsmith import Client
from src.deps import jwt_dependency

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv

load_dotenv()

callbacks = [
  LangChainTracer(
    project_name="raw-llm",
    client=Client(
      api_url=os.getenv("LANGCHAIN_ENDPOINT"),
      api_key=os.getenv("LANGCHAIN_API_KEY")
    )
  )
]

router = APIRouter()

async def generator(prompt: str):
    
    # model: str = "gpt-4o-mini"
    # llm = ChatOpenAI(model=model, api_key=os.getenv("OPENAI_API_KEY"))
    model: str = "claude-3-5-sonnet-20240620"
    llm = ChatAnthropic(model_name=model, temperature=0.2, max_tokens=1024)

    promptTemplate = ChatPromptTemplate.from_messages(
        [
            ("system", "You're an assistant. Bold key terms in your responses."),
            ("human", "{input}"),
        ]
    )

    messages = promptTemplate.format_messages(input=prompt)

    async for evt in llm.astream_events(messages, version="v1", config={"callbacks": callbacks}, model=model):
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
                "event": "on_chat_model_end"
            }, separators=(',', ':'))

@router.post("/completion")
@limiter.limit("10/minute")
def prompt(prompt: Prompt, jwt: jwt_dependency, request: Request):
    return StreamingResponse(generator(prompt.prompt), media_type='text/event-stream')