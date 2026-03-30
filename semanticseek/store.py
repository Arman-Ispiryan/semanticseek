"""
store.py — ChromaDB vector store interface.
"""

import hashlib
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings


_client_cache: Dict[str, chromadb.PersistentClient] = {}


def get_client(db_path: str) -> chromadb.PersistentClient:
    if db_path not in _client_cache:
        _client_cache[db_path] = chromadb.PersistentClient(
            path=db_path,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client_cache[db_path]


def get_collection(db_path: str):
    client = get_client(db_path)
    return client.get_or_create_collection(
        name="documents",
        metadata={"hnsw:space": "cosine"},
    )


def _chunk_id(file_path: str, chunk_index: int) -> str:
    """Stable unique ID for a chunk."""
    raw = f"{file_path}::{chunk_index}"
    return hashlib.md5(raw.encode()).hexdigest()


def _file_id(file_path: str) -> str:
    return hashlib.md5(file_path.encode()).hexdigest()


def is_indexed(collection, file_path: str) -> bool:
    """Check if any chunks from this file already exist in the collection."""
    fid = _file_id(file_path)
    results = collection.get(where={"file_hash": fid}, limit=1)
    return len(results["ids"]) > 0


def upsert_chunks(collection, file_path: str, chunks: List[Dict], embeddings: List[List[float]]):
    """Insert or update all chunks for a file."""
    fid = _file_id(file_path)

    # Remove old chunks for this file before re-inserting
    try:
        old = collection.get(where={"file_hash": fid})
        if old["ids"]:
            collection.delete(ids=old["ids"])
    except Exception:
        pass

    ids = [_chunk_id(file_path, c["chunk_index"]) for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [
        {
            "file": c["file"],
            "file_hash": fid,
            "file_name": c["file_name"],
            "extension": c["extension"],
            "chunk_index": c["chunk_index"],
        }
        for c in chunks
    ]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )


def get_stats(collection) -> Dict[str, Any]:
    """Return basic stats about the collection."""
    all_items = collection.get()
    total_chunks = len(all_items["ids"])
    unique_files = len(set(
        m["file"] for m in (all_items["metadatas"] or [])
    ))
    return {
        "total_chunks": total_chunks,
        "unique_files": unique_files,
    }
