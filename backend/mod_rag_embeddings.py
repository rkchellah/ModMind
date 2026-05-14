from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer
from supabase import create_client, Client

load_dotenv()

_model = SentenceTransformer("all-MiniLM-L6-v2")
_supabase: Client = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_KEY"],
)

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


@dataclass
class Document:
    content: str
    metadata: dict[str, Any]


@dataclass
class RetrievedChunk:
    id: int
    content: str
    metadata: dict[str, Any]
    similarity: float


def embed(text: str) -> list[float]:
    """Embed a single string using sentence-transformers all-MiniLM-L6-v2."""
    return _model.encode(text).tolist()


def index_documents(documents: list[Document]) -> None:
    """Store documents with their embeddings into Supabase."""
    rows = [
        {
            "content": doc.content,
            "metadata": doc.metadata,
            "embedding": embed(doc.content),
        }
        for doc in documents
    ]
    result = _supabase.table("mod_knowledge").insert(rows).execute()
    if not result.data:
        raise RuntimeError(
            "Supabase insert returned no data — "
            "check your table schema and RLS settings"
        )


def retrieve(query: str, k: int = 3) -> list[RetrievedChunk]:
    """Find the k most similar past mod decisions for a given query string."""
    query_embedding = embed(query)
    result = _supabase.rpc(
        "match_mod_knowledge",
        {"query_embedding": query_embedding, "match_count": k},
    ).execute()

    if result.data is None:
        return []

    return [
        RetrievedChunk(
            id=row["id"],
            content=row["content"],
            metadata=row["metadata"],
            similarity=row["similarity"],
        )
        for row in result.data
    ]