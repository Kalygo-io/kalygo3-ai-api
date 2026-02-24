import aiohttp
import os


async def fetch_embedding(token: str, prompt: str):
    """
    Call the embeddings API to get a vector for *prompt*.

    Sends the caller's token as both a cookie and an Authorization
    header so the embeddings API can authenticate regardless of which
    method it checks.
    """
    url = f"{os.getenv('EMBEDDINGS_API_URL')}/huggingface/embedding"

    payload = {"input": prompt}
    headers = {}
    cookies = {}

    if token:
        headers["Authorization"] = f"Bearer {token}"
        cookies["jwt"] = token

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url, json=payload, headers=headers, cookies=cookies
        ) as response:
            result = await response.json()
            embedding = result['embedding']

            # The API may return a batch: [[0.1, …]] for a single input.
            # Pinecone expects a flat list of floats.
            if embedding and isinstance(embedding[0], list):
                embedding = embedding[0]

            return embedding