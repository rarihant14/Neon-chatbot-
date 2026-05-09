# ============================================================
# backend/db/memory_store.py
# NeuroAgent - Long-Term Memory via Pinecone
# ============================================================
# Stores and retrieves semantic memories per user in Pinecone.
# Each memory is embedded and stored with the username as a
# namespace so users only ever see their own memories.
# ============================================================

import os
import json
import math
import re
import hashlib
from datetime import datetime
from typing import Optional

from pinecone import Pinecone, ServerlessSpec
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from backend.config import (
    PINECONE_API_KEY,
    PINECONE_INDEX_NAME,
    GEMINI_API_KEY,
    PINECONE_DIMENSION,
)

# ── Module-level singletons (lazy-initialised) ────────────────
_pinecone_client: Optional[Pinecone] = None
_index = None
_embedder: Optional[GoogleGenerativeAIEmbeddings] = None
_embedder_mode: str = "google"  # "google" | "local"
_memory_available = False   # Flips to True once connected


def _local_embed(text: str, dim: int = 768) -> list[float]:
    vec = [0.0] * dim
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    if not tokens:
        return vec

    for tok in tokens:
        h = hashlib.sha256(tok.encode("utf-8")).digest()
        idx = int.from_bytes(h[:4], "big") % dim
        sgn = 1.0 if (h[4] & 1) == 0 else -1.0
        vec[idx] += sgn

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _init_pinecone():
    """
    Lazily initialise the Pinecone client and embedding model.
    Called on the first actual memory operation.
    """
    global _pinecone_client, _index, _embedder, _memory_available

    if _memory_available:
        return  # Already set up

    if not PINECONE_API_KEY:
        print("[Memory] PINECONE_API_KEY missing — memory disabled.")
        return

    try:
        # Connect to Pinecone
        _pinecone_client = Pinecone(api_key=PINECONE_API_KEY)

        # Create index if it doesn't exist yet
        existing = [idx.name for idx in _pinecone_client.list_indexes()]
        if PINECONE_INDEX_NAME not in existing:
            _pinecone_client.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=PINECONE_DIMENSION,
                metric="cosine",
                spec=ServerlessSpec(cloud="aws", region="us-east-1"),
            )
            print(f"[Memory] Created Pinecone index: {PINECONE_INDEX_NAME}")

        _index = _pinecone_client.Index(PINECONE_INDEX_NAME)

        # Embedding model: prefer Gemini, fall back to local embeddings when Gemini is unavailable.
        global _embedder_mode
        if GEMINI_API_KEY:
            try:
                _embedder = GoogleGenerativeAIEmbeddings(
                    model="models/embedding-001",
                    google_api_key=GEMINI_API_KEY,
                )
                _embedder_mode = "google"
            except Exception as e:
                print(f"[Memory] Gemini embedding init failed — using local embeddings: {e}")
                _embedder = None
                _embedder_mode = "local"
        else:
            _embedder = None
            _embedder_mode = "local"

        _memory_available = True
        print(f"[Memory] Pinecone connected successfully. Embeddings: {_embedder_mode}")

    except Exception as e:
        print(f"[Memory] Pinecone init failed: {e}")
        _memory_available = False


def _embed(text: str) -> list[float]:
    """Return embedding vector for `text`."""
    if _embedder is not None:
        return _embedder.embed_query(text)
    return _local_embed(text, dim=PINECONE_DIMENSION)


def store_memory(username: str, text: str, metadata: dict = None) -> bool:
    """
    Embed `text` and upsert it into Pinecone under the user's namespace.
    Returns True on success, False if memory is unavailable.
    """
    _init_pinecone()
    if not _memory_available:
        return False

    try:
        vector = _embed(text)
        doc_id = f"{username}_{datetime.utcnow().timestamp()}"

        meta = {
            "username": username,
            "text": text,
            "timestamp": datetime.utcnow().isoformat(),
        }
        if metadata:
            meta.update(metadata)

        _index.upsert(
            vectors=[{"id": doc_id, "values": vector, "metadata": meta}],
            namespace=username,   # User-scoped namespace
        )
        return True

    except Exception as e:
        print(f"[Memory] store_memory error: {e}")
        return False


def retrieve_memories(username: str, query: str, top_k: int = 5) -> list[dict]:
    """
    Retrieve the `top_k` most semantically similar memories for `username`.
    Returns a list of {'text': ..., 'score': ..., 'timestamp': ...} dicts.
    """
    _init_pinecone()
    if not _memory_available:
        return []

    try:
        query_vector = _embed(query)
        results = _index.query(
            vector=query_vector,
            top_k=top_k,
            namespace=username,
            include_metadata=True,
        )

        memories = []
        for match in results.matches:
            if match.score > 0.5:   # Only include relevant matches
                memories.append({
                    "text": match.metadata.get("text", ""),
                    "score": round(match.score, 3),
                    "timestamp": match.metadata.get("timestamp", ""),
                })

        return memories

    except Exception as e:
        print(f"[Memory] retrieve_memories error: {e}")
        return []


def delete_user_memories(username: str) -> bool:
    """Delete ALL memories stored under a user's namespace."""
    _init_pinecone()
    if not _memory_available:
        return False

    try:
        _index.delete(delete_all=True, namespace=username)
        print(f"[Memory] Deleted all memories for: {username}")
        return True
    except Exception as e:
        print(f"[Memory] delete_user_memories error: {e}")
        return False


def is_available() -> bool:
    """Return whether Pinecone memory is functional."""
    _init_pinecone()
    return _memory_available
