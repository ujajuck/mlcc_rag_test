"""
search_rag tool using ChromaDB + internal embedding API.
This version queries the Chroma collection populated from mlcc_catalog_rag_chunks_v2.jsonl 
and uses internal embedding API for query vectorization.
"""

from pathlib import Path
import os
from typing import Any, Dict, List
import chromadb
import requests
from dotenv import load_dotenv

# -------------------------------------------------------------------
# Env / paths
# -------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

_DB_DIR = Path(os.getenv("CHROMA_DB_DIR", _PROJECT_ROOT / "chroma_db"))
_COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "semco_mlcc_catalog_2025")

TEXT_EMBEDDING_MODEL_URL = os.getenv("TEXT_EMBEDDING_MODEL_URL", "")
TEXT_EMBEDDING_MODEL_NAME = os.getenv("TEXT_EMBEDDING_MODEL_NAME", "/mnt/BGE-M3-KOR/")
TEXT_EMBEDDING_API_KEY = os.getenv("TEXT_EMBEDDING_API_KEY", "")
TEXT_EMBEDDING_TIMEOUT_SEC = int(os.getenv("TEXT_EMBEDDING_TIMEOUT_SEC", "30"))

_client = None
_collection = None


def _get_text_embedding(text_list: List[str]) -> Dict[str, Any]:
    """Get embeddings from internal embedding API."""
    try:
        response = requests.post(
            TEXT_EMBEDDING_MODEL_URL,
            json={
                "input": text_list, 
                "model": TEXT_EMBEDDING_MODEL_NAME
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": TEXT_EMBEDDING_API_KEY,
            },
            timeout=TEXT_EMBEDDING_TIMEOUT_SEC,
        )
        response.raise_for_status()
        
        payload = response.json()
        res_data = payload.get("data", [])
        embeddings: List[List[float]] = [item.get("embedding", []) for item in res_data]
        
        return {"status": "success", "outputs": embeddings}
    
    except Exception as e:
        return {"status": "error", "error": str(e), "outputs": []}


def _get_collection():
    """Lazy-init Chroma collection handle."""
    global _client, _collection
    
    if _collection is not None:
        return _collection
    
    try:
        _client = chromadb.PersistentClient(path=str(_DB_DIR))
        _collection = _client.get_collection(name=_COLLECTION_NAME)
        return _collection
    except Exception:
        return None


def search_rag(query: str, top_k: int = 5) -> dict:
    """
    Search the SEMCO MLCC catalog vector DB. 
    Retrieves chunks from the MLCC catalog that are relevant to the query. 
    
    Args:
        query: Natural-language or code-based search query.
        top_k: Number of results to return.
    """
    query = (query or "").strip()
    
    if not query:
        return {
            "status": "error",
            "error": "query is empty.",
            "query": query,
            "result_count": 0,
            "results": [],
        }

    if top_k <= 0:
        top_k = 5

    collection = _get_collection()
    if collection is None:
        return {
            "status": "error",
            "error": f"Chroma collection not available. db_dir={_DB_DIR}, collection={_COLLECTION_NAME}",
            "query": query,
            "result_count": 0,
            "results": [],
        }

    # 1. Get Query Embedding
    emb_res = _get_text_embedding([query])
    if emb_res.get("status") != "success":
        return {
            "status": "error",
            "error": f"embedding failed: {emb_res.get('error')}",
            "query": query,
            "result_count": 0,
            "results": [],
        }

    outputs = emb_res.get("outputs", [])
    if not outputs or not outputs[0]:
        return {
            "status": "error",
            "error": "embedding output is empty.",
            "query": query,
            "result_count": 0,
            "results": [],
        }

    query_emb = outputs[0]

    # 2. Vector Search
    try:
        resp = collection.query(
            query_embeddings=[query_emb],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        return {
            "status": "error",
            "error": f"vector query failed: {e}",
            "query": query,
            "result_count": 0,
            "results": [],
        }

    # 3. Parse Results
    docs = (resp.get("documents") or [[]])[0]
    metas = (resp.get("metadatas") or [[]])[0]
    dists = (resp.get("distances") or [[]])[0]
    ids = (resp.get("ids") or [[]])[0]

    results = []
    for i in range(len(docs)):
        dist = dists[i] if i < len(dists) else None
        # Convert distance to a similarity score (approximate)
        score = None if dist is None else round(1.0 / (1.0 + float(dist)), 4)
        
        chunk_id = ids[i] if i < len(ids) else "unknown"
        if i < len(metas) and isinstance(metas[i], dict):
            chunk_id = metas[i].get("id", chunk_id)

        results.append({
            "chunk_id": chunk_id,
            "score": score,
            "text": (docs[i] or "")[:2000],
        })

    return {
        "status": "success",
        "query": query,
        "result_count": len(results),
        "results": results,
    }