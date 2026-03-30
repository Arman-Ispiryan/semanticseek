"""
searcher.py — Semantic search over indexed chunks.
"""

from typing import List, Dict
from sentence_transformers import SentenceTransformer

_model_cache = {}


def get_model(model_name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    if model_name not in _model_cache:
    _model_cache[model_name] = SentenceTransformer(model_name, device="cpu")
    return _model_cache[model_name]


def search(collection, query: str, top_k: int = 5, model_name: str = "all-MiniLM-L6-v2") -> List[Dict]:
    """
    Embed the query and find the top_k most similar chunks.
    Returns deduplicated results ranked by best chunk score per file.
    """
    model = get_model(model_name)
    query_embedding = model.encode([query], show_progress_bar=False)[0].tolist()

    # Fetch more than needed to allow deduplication across files
    fetch_k = min(top_k * 6, 50)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=fetch_k,
        include=["documents", "metadatas", "distances"],
    )

    ids = results["ids"][0]
    docs = results["documents"][0]
    metas = results["metadatas"][0]
    distances = results["distances"][0]

    # ChromaDB cosine distance: score = 1 - distance (higher = more similar)
    scored = []
    for doc, meta, dist in zip(docs, metas, distances):
        score = 1.0 - dist
        scored.append({
            "file": meta["file"],
            "file_name": meta["file_name"],
            "extension": meta["extension"],
            "chunk_index": meta["chunk_index"],
            "snippet": doc,
            "score": round(score, 4),
        })

    # Deduplicate: keep best-scoring chunk per file
    seen_files = {}
    for item in scored:
        f = item["file"]
        if f not in seen_files or item["score"] > seen_files[f]["score"]:
            seen_files[f] = item

    # Sort by score descending, return top_k
    deduped = sorted(seen_files.values(), key=lambda x: x["score"], reverse=True)
    return deduped[:top_k]
