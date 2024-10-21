from typing import Any, Optional
from fastapi import APIRouter, Request
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_postgres import PostgresChatMessageHistory

from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.classes.agent import Agent
from src.core.schemas.DesignAndRunSwarm.RunSwarmPrompt import RunCrewPrompt

import json
import os

from fastapi.responses import StreamingResponse

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.callbacks import LangChainTracer
import psycopg
from src.deps import jwt_dependency

limiter = Limiter(key_func=get_remote_address)

from dotenv import load_dotenv
import uuid

load_dotenv()

callbacks = []

router = APIRouter()

async def generator(sessionId: str, prompt: str, agentsConfig: dict, flowConfig: str):

    llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv("OPENAI_API_KEY"))
    # model = ChatAnthropic(model="claude-3-5-sonnet-20240620", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))

    agents = []

    for a in agentsConfig:
        agents.append(Agent(
            agent_name=a['name'],
            system_prompt=a['system_prompt'],
            llm=llm,
        ))

    flow = flowConfig

    agents = {agent.name: agent for agent in agents}
    tasks = flow.split("->")
    current_task = prompt
    loop_count = 0

    print('tasks', tasks)

    while loop_count < 1:
        for task in tasks:

            print('task', task)

            agent_names = [
                name.strip() for name in task.split(",")
            ]
            if len(agent_names) > 1:
                # Parallel processing
                print(
                    f"Running agents in parallel: {agent_names}"
                )

                parallel_group_id = str(uuid.uuid4())

                results = []
                for agent_name in agent_names:
                    agent = agents[agent_name]
                    result = None
                    # As the current `swarms` package is using LangChain v0.1 we need to use the v0.1 version of the `astream_events` API
                    # Below is the link to the `astream_events` spec as outlined in the LangChain v0.1 docs
                    # https://python.langchain.com/v0.1/docs/expression_language/streaming/#event-reference
                    # Below is the link to the `astream_events` spec as outlined in the LangChain v0.2 docs
                    # https://python.langchain.com/v0.2/docs/versions/v0_2/migrating_astream_events/
                    async for evt in agent.astream_events(
                        f"SYSTEM: {agent.system_prompt}\nINPUT: {current_task}\nAI: ", version="v1"
                    ):
                        # print(evt) # <- useful when building/debugging
                        
                        # if evt["event"] == "on_llm_end":
                        #     result = evt["data"]["output"]
                        #     print(agent.name, result)

                        if evt["event"] == "on_chat_model_start":
                            yield json.dumps({
                                "parallel_group_id": parallel_group_id,
                                "event": "on_chat_model_start",
                                "run_id": evt['run_id'],
                                "agent_name": agent.name
                            }, separators=(',', ':'))

                        elif evt["event"] == "on_chat_model_stream":
                            yield json.dumps({
                                "parallel_group_id": parallel_group_id,
                                "event": "on_chat_model_stream",
                                "run_id": evt['run_id'],
                                "agent_name": agent.name,
                                "data": evt["data"]['chunk'].content
                            }, separators=(',', ':'))

                        elif evt["event"] == "on_chat_model_end":
                            result = evt["data"]["output"].content
                            print(agent.name, "result", result)
                            yield json.dumps({
                                "event": "on_chat_model_end",
                                "run_id": evt['run_id']
                            }, separators=(',', ':'))
                    results.append(result)

                current_task = ""
                for index, res in enumerate(results):
                    print("enumerating...")
                    print('index', index)
                    print('agent_names', agent_names),
                    print('res', res)

                    current_task += (
                        "# OUTPUT of "
                        + agent_names[index]
                        + ""
                        + res
                        + "\n\n"
                    )
            else:
                # Sequential processing
                print(
                    f"Running agents sequentially: {agent_names}"
                )
                agent_name = agent_names[0]
                agent = agents[agent_name]
                result = None

                # As the current `swarms` package is using LangChain v0.1 we need to use the v0.1 version of the `astream_events` API
                # Below is the link to the `astream_events` spec as outlined in the LangChain v0.1 docs
                # https://python.langchain.com/v0.1/docs/expression_language/streaming/#event-reference
                # Below is the link to the `astream_events` spec as outlined in the LangChain v0.2 docs
                # https://python.langchain.com/v0.2/docs/versions/v0_2/migrating_astream_events/
                async for evt in agent.astream_events(
                    f"SYSTEM: {agent.system_prompt}\nINPUT: {current_task}\nAI: ",
                    version="v1",
                ):
                    # print(evt) # <- useful when building/debugging

                    if evt["event"] == "on_chat_model_start":
                        yield json.dumps({
                            "event": "on_chat_model_start",
                            "run_id": evt['run_id'],
                            "agent_name": agent.name
                        }, separators=(',', ':'))

                    elif evt["event"] == "on_chat_model_stream":
                        print('on_chat_model_stream', evt["data"]['chunk'].content)
                        yield json.dumps({
                            "event": "on_chat_model_stream",
                            "data": evt["data"]['chunk'].content,
                            "run_id": evt['run_id']
                        }, separators=(',', ':'))

                    elif evt["event"] == "on_chat_model_end":
                        result = evt["data"]["output"].content
                        # print(agent.name, "result", result)
                        yield json.dumps({
                            "event": "on_chat_model_end",
                            "run_id": evt['run_id']
                        }, separators=(',', ':'))
                current_task += (
                        "# OUTPUT of "
                        + agent_name
                        + ""
                        + result
                        + "\n\n"
                    )
        loop_count += 1

@router.post("/stream")
@limiter.limit("10/minute")
def streamHierarchical(prompt: RunCrewPrompt, jwt: jwt_dependency, request: Request):
    
    print('streamHierarchical')

    return StreamingResponse(generator(prompt.sessionId, prompt.content, prompt.agentsConfig, prompt.flow), media_type='text/event-stream')