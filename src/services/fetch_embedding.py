import aiohttp
import os 

async def fetch_embedding(jwt: str, prompt: str):
    url = f"{os.getenv('EMBEDDING_API_URL')}/huggingface/embedding"
    payload = {"input": prompt}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, cookies={
            "jwt": jwt
        }) as response:
            result = await response.json()
            return result['embedding']