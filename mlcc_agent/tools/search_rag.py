"""Mock search_rag tool for testing.

In production, this tool queries the SEMCO MLCC vector DB
(collection: semco_mlcc_part1_2025) built from mlcc_catalog_rag_chunks.jsonl.

This mock implementation performs simple keyword matching against the
local JSONL file so the agent workflow can be tested end-to-end
without a real vector DB.
"""

import json
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CHUNKS_PATH = _PROJECT_ROOT / "mlcc_catalog_rag_chunks.jsonl"

_chunks: list[dict] | None = None


def _load_chunks() -> list[dict]:
    global _chunks
    if _chunks is not None:
        return _chunks

    _chunks = []
    if _CHUNKS_PATH.is_file():
        with open(_CHUNKS_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        _chunks.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return _chunks


def search_rag(query: str, top_k: int = 5) -> dict:
    """Search the SEMCO MLCC catalog vector DB.

    Retrieves chunks from the MLCC catalog that are relevant to the query.
    The catalog covers part numbering codes, product families, reliability
    levels, new-product examples, and caution characteristics.

    In the test environment this performs keyword matching against the
    local chunk file. In production it queries the actual vector DB.

    Args:
        query: Natural-language or code-based search query.
               Examples: "A X5R 온도특성 코드", "0201 0603 4.7uF X5R 4V",
               "온도특성 A X5R", "high level II outdoor 85 85 1000h"
        top_k: Maximum number of chunks to return (default 5).

    Returns:
        A dict with 'status', 'query', 'result_count', and 'results'.
        Each result contains 'chunk_id', 'score', and 'text'.
    """
    chunks = _load_chunks()
    if not chunks:
        return {
            "status": "error",
            "error": (
                f"Chunk file not found or empty at {_CHUNKS_PATH}. "
                "Make sure mlcc_catalog_rag_chunks.jsonl exists in the project root."
            ),
        }

    keywords = query.lower().split()
    scored: list[tuple[float, dict]] = []

    for chunk in chunks:
        text = chunk.get("text", "").lower()
        metadata = chunk.get("metadata", {})
        aliases = " ".join(metadata.get("aliases", [])).lower()
        searchable = text + " " + aliases

        hits = sum(1 for kw in keywords if kw in searchable)
        if hits > 0:
            score = hits / len(keywords)
            scored.append((score, chunk))

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    results = []
    for score, chunk in top:
        results.append({
            "chunk_id": chunk.get("id", "unknown"),
            "score": round(score, 3),
            "text": chunk.get("text", "")[:2000],
        })

    return {
        "status": "success",
        "query": query,
        "result_count": len(results),
        "results": results,
    }
