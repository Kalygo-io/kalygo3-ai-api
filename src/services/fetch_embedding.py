import aiohttp
import os 

async def fetch_embedding(jwt: str, prompt: str):
    url = f"{os.getenv('EMBEDDINGS_API_URL')}/huggingface/embedding"

    print('fetch_embedding', url)

    payload = {"input": prompt}
    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, cookies={
            "jwt": jwt
        }) as response:
            result = await response.json()
            return result['embedding']