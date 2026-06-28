"""
Tests for the per-namespace file breakdown endpoint and its aggregation helper.

Pinecone is external, so the live-scan path is exercised with a fake index; the
ingestion-log fallback runs against the real test DB.
"""
import pytest

import src.routers.vectorStores.list_namespace_files as nf
from src.db.models import VectorDbIngestionLog
from src.routers.vectorStores.list_namespace_files import (
    aggregate_filename_counts,
    filename_of,
    NO_FILENAME,
)

IDX = "all-minilm-l6-v2-384-dims"
NS = "bolay"
URL = f"/api/vector-stores/indexes/{IDX}/namespaces/{NS}/files"


# ── pure helpers ─────────────────────────────────────────────────────

def test_filename_of_buckets_missing():
    assert filename_of({"filename": "a.md"}) == "a.md"
    assert filename_of({}) == NO_FILENAME
    assert filename_of(None) == NO_FILENAME
    assert filename_of({"filename": ""}) == NO_FILENAME


def test_aggregate_counts_by_filename():
    metas = [
        {"filename": "a.md"},
        {"filename": "a.md"},
        {"filename": "b.csv"},
        {},          # → (no filename)
        None,        # → (no filename)
    ]
    assert aggregate_filename_counts(metas) == {"a.md": 2, "b.csv": 1, NO_FILENAME: 2}


# ── endpoint: live scan (mocked Pinecone) ────────────────────────────

class _FakeIndex:
    def __init__(self, ns_counts, metas, raise_on_list=False):
        self._ns_counts = ns_counts
        self._metas = metas
        self._raise_on_list = raise_on_list

    def describe_index_stats(self):
        return {
            "dimension": 384,
            "namespaces": {ns: {"vector_count": c} for ns, c in self._ns_counts.items()},
        }

    def list_paginated(self, namespace=None, limit=None, pagination_token=None):
        if self._raise_on_list:
            raise RuntimeError("list not supported")
        ids = list(self._metas.keys())
        return type("Page", (), {
            "vectors": [type("V", (), {"id": i})() for i in ids],
            "pagination": None,
        })()

    def fetch(self, ids=None, namespace=None):
        vectors = {i: type("Vec", (), {"metadata": self._metas.get(i)})() for i in (ids or [])}
        return type("FR", (), {"vectors": vectors})()


def _patch_pinecone(monkeypatch, fake_index):
    class _FakePinecone:
        def __init__(self, *a, **k):
            pass

        def Index(self, name):
            return fake_index

    monkeypatch.setattr(nf, "Pinecone", _FakePinecone)
    monkeypatch.setattr(nf, "get_pinecone_api_key", lambda *a, **k: "fake-key")


@pytest.fixture(autouse=True)
def _clear_cache():
    nf._CACHE.clear()
    yield
    nf._CACHE.clear()


async def test_live_scan_groups_by_filename(authed_client, monkeypatch):
    fake = _FakeIndex(
        ns_counts={NS: 4},
        metas={
            "v1": {"filename": "a.md"},
            "v2": {"filename": "a.md"},
            "v3": {"filename": "b.csv"},
            "v4": {},
        },
    )
    _patch_pinecone(monkeypatch, fake)

    resp = await authed_client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "pinecone"
    assert body["total_vectors"] == 4
    assert body["scanned_vectors"] == 4
    assert body["truncated"] is False
    # Sorted by count desc, then filename asc. The fake vectors carry no
    # upload metadata, so uploaded_at/uploaded_by are None.
    assert body["files"] == [
        {"filename": "a.md", "vector_count": 2, "uploaded_at": None, "uploaded_by": None},
        {"filename": NO_FILENAME, "vector_count": 1, "uploaded_at": None, "uploaded_by": None},
        {"filename": "b.csv", "vector_count": 1, "uploaded_at": None, "uploaded_by": None},
    ]


async def test_empty_namespace_returns_no_files(authed_client, monkeypatch):
    _patch_pinecone(monkeypatch, _FakeIndex(ns_counts={}, metas={}))
    resp = await authed_client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_vectors"] == 0
    assert body["files"] == []


async def test_falls_back_to_ingestion_log_on_scan_error(
    authed_client, db, monkeypatch
):
    # Pinecone reports vectors but listing fails → fall back to the Postgres log.
    _patch_pinecone(monkeypatch, _FakeIndex(ns_counts={NS: 3}, metas={}, raise_on_list=True))

    log = VectorDbIngestionLog(
        account_id=1,
        provider="pinecone",
        index_name=IDX,
        namespace=NS,
        filenames=["report.csv"],
        vectors_added=3,
        vectors_deleted=0,
        vectors_failed=0,
    )
    log.operation_type = "INGEST"
    log.status = "SUCCESS"
    db.add(log)
    db.flush()

    resp = await authed_client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["source"] == "ingestion_log"
    assert len(body["files"]) == 1
    f = body["files"][0]
    assert f["filename"] == "report.csv"
    assert f["vector_count"] == 3
    # uploaded_at is derived from the log row's created_at (epoch-ms string);
    # the log has no uploader info, so uploaded_by is None.
    assert isinstance(f["uploaded_at"], str)
    assert f["uploaded_by"] is None
