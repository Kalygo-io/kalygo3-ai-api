"""
Helper service for embedding CRM data (contact events, career timeline)
into the ``crm`` namespace in Pinecone.

Each DB row becomes a single vector whose embedded text is a short,
human-readable paragraph that includes the parent contact's identity
so the embedding is semantically self-contained.

Vector IDs follow a deterministic scheme:
  contact_event_{id}
  career_timeline_{id}

This makes upserts idempotent and deletes trivial.
"""

import os
from datetime import date, datetime
from typing import Optional

from src.core.clients import pc
from src.services.fetch_embedding import fetch_embedding

PINECONE_INDEX = os.getenv("PINECONE_ALL_MINILM_L6_V2_INDEX")
CRM_NAMESPACE = "crm"


# ── Text renderers ────────────────────────────────────────────────────────────
# These convert a DB row + parent contact info into a short paragraph
# that reads well to an embedding model.


def render_contact_event_text(
    *,
    contact_name: str,
    contact_email: str,
    event_type: str,
    title: str,
    description: Optional[str],
    occurred_at: datetime,
) -> str:
    lines = [
        f"Contact: {contact_name} ({contact_email})",
        f"Event Type: {event_type.replace('_', ' ').title()}",
        f"Date: {occurred_at.strftime('%B %d, %Y')}",
        f"Title: {title}",
    ]
    if description:
        lines.append(f"Description: {description}")
    return "\n".join(lines)


def render_career_timeline_text(
    *,
    contact_name: str,
    contact_email: str,
    title: str,
    description: Optional[str],
    start_date: date,
    end_date: Optional[date],
) -> str:
    start_label = start_date.strftime("%b %Y")
    end_label = end_date.strftime("%b %Y") if end_date else "Present"
    lines = [
        f"Contact: {contact_name} ({contact_email})",
        f"Career: {title}",
        f"Period: {start_label} – {end_label}",
    ]
    if description:
        lines.append(f"Description: {description}")
    return "\n".join(lines)


# ── Pinecone operations ──────────────────────────────────────────────────────


async def upsert_contact_event_vector(
    *,
    token: str,
    event_id: int,
    account_id: int,
    contact_id: int,
    contact_name: str,
    contact_email: str,
    event_type: str,
    title: str,
    description: Optional[str],
    occurred_at: datetime,
) -> None:
    """Embed a contact event and upsert it into Pinecone."""
    text = render_contact_event_text(
        contact_name=contact_name,
        contact_email=contact_email,
        event_type=event_type,
        title=title,
        description=description,
        occurred_at=occurred_at,
    )

    embedding = await fetch_embedding(token, text)
    if not embedding or not PINECONE_INDEX:
        return

    index = pc.Index(PINECONE_INDEX)
    index.upsert(
        vectors=[(
            f"contact_event_{event_id}",
            embedding,
            {
                "source_type": "contact_event",
                "entry_id": event_id,
                "account_id": account_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "event_type": event_type,
                "occurred_at": occurred_at.isoformat(),
                "content": text,
            },
        )],
        namespace=CRM_NAMESPACE,
    )


async def upsert_career_timeline_vector(
    *,
    token: str,
    entry_id: int,
    account_id: int,
    contact_id: int,
    contact_name: str,
    contact_email: str,
    title: str,
    description: Optional[str],
    start_date: date,
    end_date: Optional[date],
) -> None:
    """Embed a career timeline entry and upsert it into Pinecone."""
    text = render_career_timeline_text(
        contact_name=contact_name,
        contact_email=contact_email,
        title=title,
        description=description,
        start_date=start_date,
        end_date=end_date,
    )

    embedding = await fetch_embedding(token, text)
    if not embedding or not PINECONE_INDEX:
        return

    index = pc.Index(PINECONE_INDEX)
    index.upsert(
        vectors=[(
            f"career_timeline_{entry_id}",
            embedding,
            {
                "source_type": "career_timeline",
                "entry_id": entry_id,
                "account_id": account_id,
                "contact_id": contact_id,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat() if end_date else "",
                "content": text,
            },
        )],
        namespace=CRM_NAMESPACE,
    )


def delete_vector(vector_id: str) -> None:
    """Remove a single vector from the crm namespace."""
    if not PINECONE_INDEX:
        return
    index = pc.Index(PINECONE_INDEX)
    index.delete(ids=[vector_id], namespace=CRM_NAMESPACE)


# ── Token extraction ─────────────────────────────────────────────────────────


def extract_token(request) -> Optional[str]:
    """Pull the JWT from cookies or the Authorization header."""
    token = request.cookies.get("jwt")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.removeprefix("Bearer ").strip()
    return token
