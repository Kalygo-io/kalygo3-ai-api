# TLDR

Kalygo 3.0 A.I. API (powered by FastAPI)

## Initial setup

- `docker network ls`
- `docker network create agent-network`
- In Cursor or VSCode (SHIFT + CMD + P -> `Build and Open in Container`)

## Alternate technique

- `docker build -f Dockerfile.dev -t kalygo-ai-api .`
- `docker run -p 4000:4000 kalygo-ai-api`

## How to run the FastAPI

- `uv sync`
- `uvicorn src.main:app --host 0.0.0.0 --port 4000 --proxy-headers --reload`

## How to kill the API running on port 4000

- `netstat -tlnp 2>/dev/null | grep :4000`
- `kill -9 <PORT_NUMBER_HERE>`

## How to save versions of top-level packages

- pip install pipreqs
- pipreqs . --force

## How to run on local

```sh
python -m venv .venv
source .venv/bin/activate
```

## Running Evaluations

### AI School Agent Q&A Evaluation

Evaluate the AI School Agent using a CSV dataset with questions and ground truth answers:

```bash
# Run evaluation with a CSV file
ENVIRONMENT=test uv run eval_remote_vs_local_agent_agent --csv evals/remote_vs_local_agent/data/ai_school_kb_qa_concise_dataset.csv

# Specify a custom dataset name
ENVIRONMENT=test uv run eval_remote_vs_local_agent_agent --csv evals/remote_vs_local_agent/data/ai_school_kb_qa_full_dataset.csv --dataset-name ai-school-agent-qa-20251201-053011

# Use existing dataset
ENVIRONMENT=test uv run eval_remote_vs_local_agent_agent --use-existing-dataset --dataset-name ai-school-agent-qa-20251201-053011

# Switch the Remote for the local agent - lines 115/116 & 568 

```

**Requirements:**
- `LANGSMITH_API_KEY`: Required for logging results to LangSmith
- `OPENAI_API_KEY`: Required for LLM-as-a-Judge evaluation
- Database access: The script will create a test account if needed

**CSV Format:**
```csv
question,ground_truth,category,difficulty,metadata
"What is Python?","Python is a programming language.","programming","easy","{}"
```

See `evals/ai_school_agent/README.md` for more details.

