from typing import Any, Optional
from fastapi import APIRouter, Request
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_postgres import PostgresChatMessageHistory
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.core.schemas.HierarchicalCrew.RunCrewPrompt import RunCrewPrompt

from crewai import Agent, Crew, Task, Process

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

async def generator(sessionId: str, prompt: str, crewConfig: dict):

    llm = ChatOpenAI(model='gpt-4o-mini', api_key=os.getenv("OPENAI_API_KEY"))
    # model = ChatAnthropic(model="claude-3-5-sonnet-20240620", anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"))

    # print()
    # print('crewConfig', crewConfig)
    # print()

    manager_agent = Agent(
        role=crewConfig["managerAgent"]["role"],
        goal=crewConfig["managerAgent"]["goal"],
        backstory=crewConfig["managerAgent"]["backstory"]
    )

    worker_agents = []

    for workerAgent in crewConfig["workerAgents"]:

        print()
        print('workerAgent', workerAgent)
        print()

        worker_agents.append(
            Agent(
                role=workerAgent["role"],
                goal=workerAgent["goal"],
                backstory=workerAgent["backstory"],
                verbose=True
            )
        )

    research_task = Task(
        description="""
Conduct a thorough research about AI and its impact on the world.
    
- Make sure some research is done by the Le Nouvelliste reporter.
- Make sure some research is done by the Loop News Haiti reporter.
        """,
        expected_output="""
5 Bulletpoints of the top 5 events
        """,
    )

    def callback(step):
        print('___ --- ___')
        print('step', step)
        print('___ --- ___')

    crew = Crew(
        agents=worker_agents,
        manager_agent=manager_agent,
        tasks=[research_task],
        process=Process.hierarchical,
        verbose=True,
        # step_callback=(lambda step: callback(step))
    )

    crew_output = crew.kickoff()

    print()
    print('FINAL OUTPUT')
    print()
    print(crew_output)
    print()
    print()

    yield json.dumps({
        "event": "error",
    }, separators=(',', ':'))

@router.post("/stream")
@limiter.limit("10/minute")
def streamHierarchical(prompt: RunCrewPrompt, jwt: jwt_dependency, request: Request):
    return StreamingResponse(generator(prompt.sessionId, prompt.content, prompt.crewConfig), media_type='text/event-stream')