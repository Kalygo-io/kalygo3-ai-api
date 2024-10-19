from datetime import timedelta, datetime, timezone
from src.services import fetch_embedding
from pinecone import Pinecone
import os
from src.db.models import Account, Logins
import hashlib

async def record_login(account_id: int, account_email: str, ip_address: str, db):
    print(f"Recording login for account {account_email}... ")

    created_at = datetime.now()
    log = f"{ip_address} {created_at}"
    # log = f"192.168.100.200 2023-03-01T05:22:45.123456-05:00"
    
    embedding = await fetch_embedding(log) # fetch embedding from EMBEDDINGS_API_URL

    print('embedding', len(embedding))

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))

    # Compare the log with the existing logs

    results = index.query(
        vector=embedding,
        top_k=1,
        include_values=False,
        include_metadata=True,
        namespace='logins',
        filter={
          "email": {"$eq": account_email}
        },
    )

    similarity_score = 1.0

    if len(results['matches']) > 0:
        print("login similarity score", results['matches'][0]['score'])
        print("log", log)

        similarity_score = results['matches'][0]['score']

    db.add(Logins(account_id=account_id, ip_address=ip_address,similarity_score=similarity_score))
    db.commit()

    # Insert the log into the Pinecone index
    
    index.upsert(
        vectors=[
            {
                "id": hashlib.sha1(log.encode('utf-8')).hexdigest(),
                "values": embedding,
                "metadata": {"email": account_email, "ip_address": ip_address, "created_at": created_at}
            },
        ],
        namespace='logins'
    )
