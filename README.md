# TLDR

Kalygo 3.0 A.I. API (powered by FastAPI)

## Initial setup

- `docker network ls`
- `docker network create agent-network`
- In Cursor or VSCode (SHIFT + CMD + P -> `Build and Open in Container`)

## How to run the FastAPI

- `pip install -r requirements.txt`
- `uvicorn src.main:app --host 0.0.0.0 --port 4000 --proxy-headers --reload`

## How to kill the API running on port 4000

- `netstat -tlnp 2>/dev/null | grep :4000`
- `kill -9 <PORT_NUMBER_HERE>`

## How to save versions of top-level packages

- pip install pipreqs
- pipreqs . --force

