from typing import Any, Optional
from fastapi import APIRouter, Request
# from langchain_anthropic import ChatAnthropic
from langchain_postgres import PostgresChatMessageHistory

from langchain_openai import ChatOpenAI

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.helpers.get_principal import get_principal
from src.core.helpers.upload_csv_to_gcs import upload_csv_to_gcs
from src.core.schemas.SpreadsheetSwarmPrompt import SpreadsheetSwarmPrompt

import json
import os

from fastapi.responses import StreamingResponse

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.callbacks import LangChainTracer
import psycopg

from src.deps import jwt_dependency
from src.core.helpers.generate_signed_url import generate_signed_url

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv
import uuid
import csv
from google.cloud import storage

load_dotenv()

callbacks = [
#   LangChainTracer(
#     project_name="streaming-with-memory-agent",
#     client=Client(
#       api_url=os.getenv("LANGCHAIN_ENDPOINT"),
#       api_key=os.getenv("LANGCHAIN_API_KEY")
#     )
#   )
]

class Agent():
    def __init__(
        self,
        llm: Optional[Any] = None,
        agent_name: Optional[str] = "",
        system_prompt: Optional[str] = ""
    ):
        self.llm = llm
        self.name = agent_name
        self.system_prompt = system_prompt
        
    async def astream_events(
        self, task: str = None, img: str = None, *args, **kwargs
    ):
        """
        Run the Agent with LangChain's astream_events API.
        Only works with LangChain-based models.
        """
        try:
            async for evt in self.llm.astream_events(task, version="v1"):
                yield evt
        except Exception as e:
            print(f"Error streaming events: {e}")

router = APIRouter()

async def generator(sessionId: str, prompt: str, agentsConfig: dict):

    print('--- generator ---')

    # llm = Anthropic(anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"), streaming=True)
    # llm = OpenAIChatLLM(model='gpt-4o-mini', api_key=os.getenv("OPENAI_API_KEY"))

    llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv("OPENAI_API_KEY"))

    # model: str = "claude-3-5-sonnet-20240620"
    # llm = ChatAnthropic(model_name=model, temperature=0.1, max_tokens=1024)
    # conn_info = os.getenv("POSTGRES_URL")
    # sync_connection = psycopg.connect(conn_info)
    # history = PostgresChatMessageHistory(
    #     'chat_history', # table name
    #     sessionId,
    #     sync_connection=sync_connection
    # )
    # promptTemplate = ChatPromptTemplate.from_messages(
    #     [
    #         ("system", "You're an assistant. Bold key terms in your responses."),
    #         MessagesPlaceholder(variable_name="history"),
    #         ("human", "{input}"),
    #     ]
    # )
    # messages = promptTemplate.format_messages(input=prompt, history=history.messages)

    # vvv SEQUENTIAL SWARM vvv

    agents = []
    for agent in agentsConfig:
        agents.append(Agent(
            agent_name=agent['name'],
            system_prompt=agent['system_prompt'],
            llm=llm,
        ))

    print(prompt)
    loop_count = 0

    for_csv = "agent,output\n"

    while loop_count < 1:
        results = []
        for agent in agents:

            print('agent', agent.name)

            result = None
            # As the current `swarms` package is using LangChain v0.1 we need to use the v0.1 version of the `astream_events` API
            # Below is the link to the `astream_events` spec as outlined in the LangChain v0.1 docs
            # https://python.langchain.com/v0.1/docs/expression_language/streaming/#event-reference
            # Below is the link to the `astream_events` spec as outlined in the LangChain v0.2 docs
            # https://python.langchain.com/v0.2/docs/versions/v0_2/migrating_astream_events/
            async for evt in agent.astream_events(
                f"SYSTEM: {agent.system_prompt}\nINPUT: {prompt}\nAI: ", version="v1"
            ):
                # print(evt) # <- useful when building/debugging
                
                # if evt["event"] == "on_llm_end":
                #     result = evt["data"]["output"]
                #     print(agent.name, result)

                if evt["event"] == "on_chat_model_start":
                    yield json.dumps({
                        "event": "on_chat_model_start",
                        "run_id": evt['run_id'],
                        "agent_name": agent.name
                    }, separators=(',', ':'))

                elif evt["event"] == "on_chat_model_stream":
                    yield json.dumps({
                        "event": "on_chat_model_stream",
                        "run_id": evt['run_id'],
                        "agent_name": agent.name,
                        "data": evt["data"]['chunk'].content
                    }, separators=(',', ':'))

                elif evt["event"] == "on_chat_model_end":
                    final_output = evt["data"]["output"].content

                    final_output = final_output.replace('"', '""')
                    final_output = f'"{final_output}"'
                    for_csv += agent.name + "," + final_output + "\n"

                    yield json.dumps({
                        "event": "on_chat_model_end",
                        "run_id": evt['run_id']
                    }, separators=(',', ':'))
            results.append(result)

        loop_count += 1

    # Specify the GCS bucket name and file name
    bucket_name = 'swarms'
    file_name = str(uuid.uuid4()) + '.csv'

    # Upload CSV data to GCS
    upload_csv_to_gcs(for_csv, bucket_name, file_name)

    signed_url = generate_signed_url(bucket_name, file_name)

    yield json.dumps({
        "event": "add_download_link_button",
        "link": signed_url
    }, separators=(',', ':'))

@router.post("/stream")
@limiter.limit("10/minute")
def streamSpreadsheetSwarm(prompt: SpreadsheetSwarmPrompt, jwt: jwt_dependency, request: Request):
    return StreamingResponse(generator(prompt.sessionId, prompt.content, prompt.agentsConfig), media_type='text/event-stream')