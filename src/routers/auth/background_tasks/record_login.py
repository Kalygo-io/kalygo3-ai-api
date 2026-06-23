import logging
from datetime import datetime
from src.services import fetch_embedding
from pinecone import Pinecone
import os
from src.db.models import Logins
import hashlib

logger = logging.getLogger(__name__)


async def record_login(account_id: int, account_email: str, ip_address: str, db, token: str | None = None):
    created_at = datetime.now()
    log = f"{ip_address} {created_at}"

    embedding = await fetch_embedding(token, log)

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    index = pc.Index(os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX"))

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
        logger.info("Login similarity score: %s for %s", results['matches'][0]['score'], account_email)
        similarity_score = results['matches'][0]['score']

    db.add(Logins(account_id=account_id, ip_address=ip_address, similarity_score=similarity_score))
    db.commit()

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
