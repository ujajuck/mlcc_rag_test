"""
search_rag tool using ChromaDB + internal embedding API.

Two data tiers are available via the `collection` parameter:
- "context" (default): context-only collection — family, caution, dimension, etc.
  Excludes mapping_core/mapping_support to reduce noise.
- "core": pure part-number mapping tables only.
  Rarely needed — catalog-codebook.md should be used instead.
- "full": the original combined collection (all chunks). Discouraged.
"""

import os
import re
from pathlib import Path
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

# Collection names for each tier
_COLLECTION_CONTEXT = os.getenv(
    "CHROMA_COLLECTION_CONTEXT", "semco_mlcc_catalog_context_2025"
)
_COLLECTION_CORE = os.getenv(
    "CHROMA_COLLECTION_CORE", "semco_mlcc_catalog_core_2025"
)
_COLLECTION_FULL = os.getenv(
    "CHROMA_COLLECTION_NAME", "semco_mlcc_catalog_2025"
)

_COLLECTION_MAP = {
    "context": _COLLECTION_CONTEXT,
    "core": _COLLECTION_CORE,
    "full": _COLLECTION_FULL,
}

TEXT_EMBEDDING_MODEL_URL = os.getenv("TEXT_EMBEDDING_MODEL_URL", "")
TEXT_EMBEDDING_MODEL_NAME = os.getenv("TEXT_EMBEDDING_MODEL_NAME", "/mnt/BGE-M3-KOR/")
TEXT_EMBEDDING_API_KEY = os.getenv("TEXT_EMBEDDING_API_KEY", "")
TEXT_EMBEDDING_TIMEOUT_SEC = int(os.getenv("TEXT_EMBEDDING_TIMEOUT_SEC", "30"))

_client = None
_collections: dict[str, Any] = {}

# Code-mapping detection patterns — triggers codebook hint
_CODE_MAPPING_PATTERNS = re.compile(
    r"(size.?code|voltage.?code|temperature.?code|capacitance.?code|"
    r"tolerance.?code|thickness.?code|온도특성.?코드|전압.?코드|용량.?코드|"
    r"편차.?코드|사이즈.?코드|두께.?코드|position\s*[1-7]|"
    r"\b(1st|2nd|3rd|4th|5th|6th|7th)\s*code)",
    re.IGNORECASE,
)

# Session call counter for budget tracking
_call_count = 0
_CALL_BUDGET = 3


def _get_text_embedding(text_list: List[str]) -> Dict[str, Any]:
    """Get embeddings from internal embedding API."""
    try:
        response = requests.post(
            TEXT_EMBEDDING_MODEL_URL,
            json={
                "input": text_list,
                "model": TEXT_EMBEDDING_MODEL_NAME,
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


def _get_collection(collection_tier: str = "context"):
    """Lazy-init Chroma collection handle for the requested tier."""
    global _client, _collections

    if collection_tier in _collections:
        return _collections[collection_tier]

    try:
        if _client is None:
            _client = chromadb.PersistentClient(path=str(_DB_DIR))

        col_name = _COLLECTION_MAP.get(collection_tier, _COLLECTION_MAP["context"])
        col = _client.get_collection(name=col_name)
        _collections[collection_tier] = col
        return col
    except Exception:
        return None


def _build_where_clause(
    search_group: str | None,
    position: int | None,
    chunk_type: str | None,
    collection_tier: str = "context",
) -> dict | None:
    """Build a ChromaDB where clause from metadata filters.

    For the 'context' tier, automatically excludes mapping_core/mapping_support
    as an extra safety net (in case the context collection still contains them).
    """
    conditions = []

    # Extra safety: if using context tier, exclude core groups
    if collection_tier == "context" and search_group is None:
        conditions.append({"search_group": {"$nin": ["mapping_core", "mapping_support"]}})

    if search_group is not None:
        conditions.append({"search_group": {"$eq": search_group}})
    if position is not None:
        conditions.append({"position": {"$eq": position}})
    if chunk_type is not None:
        conditions.append({"chunk_type": {"$eq": chunk_type}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def reset_call_counter() -> None:
    """Reset the per-session call counter. Call at session start."""
    global _call_count
    _call_count = 0


def search_rag(
    query: str,
    top_k: int = 5,
    collection: str = "context",
    search_group: str | None = None,
    position: int | None = None,
    chunk_type: str | None = None,
) -> dict:
    """Search the SEMCO MLCC catalog vector DB.

    Retrieves chunks from the MLCC catalog that are relevant to the query.

    IMPORTANT: For code mapping lookups (positions 1-7 — size, temperature,
    voltage, capacitance, tolerance, thickness), DO NOT use this tool.
    Read catalog-codebook.md directly instead.

    Use this tool only for context that the codebook does not cover:
    - Family/reliability descriptions → search_group="family_reference"
    - Anchor part examples → confirmed code combination as query
    - Caution characteristics → search_group="caution_reference"
    - Dimension details → search_group="dimension_reference"

    Always specify search_group to narrow results.
    Budget: max 2-3 calls per spec selection session.

    Args:
        query: Natural-language or code-based search query.
        top_k: Number of results to return.
        collection: Which data tier to search.
                    "context" (default): context-only — no code mapping noise.
                    "core": pure mapping tables. Rarely needed.
                    "full": all chunks. Discouraged.
        search_group: Filter by search_group metadata.
        position: Filter by part number position (1-11).
        chunk_type: Filter by chunk type.
    """
    global _call_count
    _call_count += 1

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

    col = _get_collection(collection)
    if col is None:
        return {
            "status": "error",
            "error": (
                f"Chroma collection not available for tier='{collection}'. "
                f"db_dir={_DB_DIR}"
            ),
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

    # 2. Build metadata where clause
    where_clause = _build_where_clause(
        search_group, position, chunk_type, collection
    )

    # 3. Vector Search
    try:
        query_kwargs: dict[str, Any] = {
            "query_embeddings": [query_emb],
            "n_results": top_k,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_clause is not None:
            query_kwargs["where"] = where_clause

        resp = col.query(**query_kwargs)
    except Exception as e:
        return {
            "status": "error",
            "error": f"vector query failed: {e}",
            "query": query,
            "result_count": 0,
            "results": [],
        }

    # 4. Parse Results
    docs = (resp.get("documents") or [[]])[0]
    metas = (resp.get("metadatas") or [[]])[0]
    dists = (resp.get("distances") or [[]])[0]
    ids = (resp.get("ids") or [[]])[0]

    results = []
    for i in range(len(docs)):
        dist = dists[i] if i < len(dists) else None
        score = None if dist is None else round(1.0 / (1.0 + float(dist)), 4)

        chunk_id = ids[i] if i < len(ids) else "unknown"
        meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
        if meta:
            chunk_id = meta.get("id", chunk_id)

        results.append({
            "chunk_id": chunk_id,
            "score": score,
            "text": (docs[i] or "")[:2000],
            "metadata": meta,
        })

    response = {
        "status": "success",
        "query": query,
        "collection": collection,
        "filters": {
            k: v for k, v in [
                ("search_group", search_group),
                ("position", position),
                ("chunk_type", chunk_type),
            ] if v is not None
        },
        "result_count": len(results),
        "results": results,
    }

    # Codebook hint: detect code-mapping queries and redirect
    if _CODE_MAPPING_PATTERNS.search(query):
        response["codebook_hint"] = (
            "This query appears to be a code mapping lookup. "
            "Use catalog-codebook.md instead of search_rag for "
            "positions 1-7. The codebook has complete tables."
        )

    # Budget warning
    if _call_count > _CALL_BUDGET:
        response["budget_warning"] = (
            f"search_rag has been called {_call_count} times this session. "
            f"Budget is {_CALL_BUDGET} calls."
        )

    return response
