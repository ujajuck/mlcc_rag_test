#!/usr/bin/env python3
"""Ingest MLCC catalog JSONL chunks into ChromaDB.

Supports dual-collection ingestion:
  - "core" collection: part-number mapping tables only
  - "context" collection: everything except mapping_core/mapping_support
  - "full" collection: all chunks combined (legacy)

Usage:
    # Ingest both core and context collections at once
    python scripts/ingest_to_chromadb.py --mode dual --reset

    # Ingest a single collection (legacy behavior)
    python scripts/ingest_to_chromadb.py --jsonl path.jsonl --collection name

    # Ingest full collection (legacy)
    python scripts/ingest_to_chromadb.py --reset
"""

import argparse
import json
import os
import sys
from pathlib import Path

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORE_JSONL = PROJECT_ROOT / "mlcc_catalog_partnumber_core_v2.jsonl"
DEFAULT_FOCUSED_JSONL = PROJECT_ROOT / "mlcc_catalog_rag_chunks_v2_partnumber_focused.jsonl"
DEFAULT_DB_DIR = PROJECT_ROOT / "chroma_db"

COLLECTION_FULL = "semco_mlcc_catalog_2025"
COLLECTION_CORE = "semco_mlcc_catalog_core_2025"
COLLECTION_CONTEXT = "semco_mlcc_catalog_context_2025"

_CORE_GROUPS = {"mapping_core", "mapping_support"}


def load_chunks(jsonl_path: Path) -> list[dict]:
    """Load chunks from a JSONL file."""
    chunks = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                chunks.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Warning: Line {lineno}: JSON parse error - {e}")
    return chunks


def flatten_metadata(meta: dict) -> dict:
    """Flatten metadata for ChromaDB (no nested lists/dicts allowed)."""
    flat = {}
    for key, value in meta.items():
        if isinstance(value, list):
            flat[key] = ", ".join(str(v) for v in value)
        elif isinstance(value, dict):
            for sub_key, sub_val in value.items():
                flat[f"{key}_{sub_key}"] = str(sub_val)
        elif value is None:
            flat[key] = ""
        else:
            flat[key] = value
    return flat


def _get_or_create_collection(client, collection_name: str):
    """Get or create a ChromaDB collection with optional custom embedding."""
    embedding_model = os.environ.get("EMBEDDING_MODEL")
    if embedding_model:
        print(f"   Using custom embedding model: {embedding_model}")
        from chromadb.utils import embedding_functions
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        return client.get_or_create_collection(
            name=collection_name, embedding_function=ef,
        )
    return client.get_or_create_collection(name=collection_name)


def _upsert_chunks(collection, chunks: list[dict], collection_name: str) -> None:
    """Upsert chunks into a ChromaDB collection."""
    ids = []
    documents = []
    metadatas = []

    for chunk in chunks:
        ids.append(chunk["id"])
        documents.append(chunk.get("text", ""))
        metadatas.append(flatten_metadata(chunk.get("metadata", {})))

    batch_size = 50
    for start in range(0, len(ids), batch_size):
        end = min(start + batch_size, len(ids))
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )
        print(f"   Upserted {end}/{len(ids)} chunks")

    final_count = collection.count()
    print(f"   Done! Collection '{collection_name}' now has {final_count} documents.\n")


def ingest_dual(db_dir: Path = DEFAULT_DB_DIR, reset: bool = False) -> None:
    """Ingest into both core and context collections."""
    # Load source files
    print(f"Loading core chunks from: {DEFAULT_CORE_JSONL}")
    core_chunks = load_chunks(DEFAULT_CORE_JSONL)
    print(f"   Loaded {len(core_chunks)} core chunks")

    print(f"Loading focused chunks from: {DEFAULT_FOCUSED_JSONL}")
    all_chunks = load_chunks(DEFAULT_FOCUSED_JSONL)
    print(f"   Loaded {len(all_chunks)} total chunks")

    # Separate context chunks (exclude core groups)
    context_chunks = [
        c for c in all_chunks
        if c.get("metadata", {}).get("search_group") not in _CORE_GROUPS
    ]
    print(f"   Filtered to {len(context_chunks)} context-only chunks")

    if not core_chunks and not context_chunks:
        print("   Nothing to ingest. Exiting.")
        sys.exit(1)

    # Connect to ChromaDB
    db_dir.mkdir(parents=True, exist_ok=True)
    print(f"ChromaDB persistent dir: {db_dir}")
    client = chromadb.PersistentClient(path=str(db_dir))

    # Reset if requested
    if reset:
        existing = [c.name for c in client.list_collections()]
        for col_name in [COLLECTION_CORE, COLLECTION_CONTEXT, COLLECTION_FULL]:
            if col_name in existing:
                client.delete_collection(col_name)
                print(f"   Deleted existing collection '{col_name}'")

    # Ingest core collection
    print(f"\nIngesting into '{COLLECTION_CORE}' ({len(core_chunks)} chunks)...")
    core_col = _get_or_create_collection(client, COLLECTION_CORE)
    _upsert_chunks(core_col, core_chunks, COLLECTION_CORE)

    # Ingest context collection
    print(f"Ingesting into '{COLLECTION_CONTEXT}' ({len(context_chunks)} chunks)...")
    context_col = _get_or_create_collection(client, COLLECTION_CONTEXT)
    _upsert_chunks(context_col, context_chunks, COLLECTION_CONTEXT)

    print("Dual ingestion complete!")
    print(f"   DB location: {db_dir}")


def ingest_single(
    jsonl_path: Path = DEFAULT_FOCUSED_JSONL,
    db_dir: Path = DEFAULT_DB_DIR,
    collection_name: str = COLLECTION_FULL,
    reset: bool = False,
) -> None:
    """Ingest into a single collection (legacy behavior)."""
    print(f"Loading chunks from: {jsonl_path}")
    chunks = load_chunks(jsonl_path)
    print(f"   Loaded {len(chunks)} chunks")

    if not chunks:
        print("   Nothing to ingest. Exiting.")
        sys.exit(1)

    db_dir.mkdir(parents=True, exist_ok=True)
    print(f"ChromaDB persistent dir: {db_dir}")
    client = chromadb.PersistentClient(path=str(db_dir))

    if reset:
        existing = [c.name for c in client.list_collections()]
        if collection_name in existing:
            client.delete_collection(collection_name)
            print(f"   Deleted existing collection '{collection_name}'")

    print(f"\nIngesting into collection '{collection_name}'...")
    col = _get_or_create_collection(client, collection_name)
    _upsert_chunks(col, chunks, collection_name)

    print(f"DB location: {db_dir}")


def main():
    parser = argparse.ArgumentParser(
        description="Ingest MLCC catalog chunks into ChromaDB"
    )
    parser.add_argument(
        "--mode",
        choices=["single", "dual"],
        default="single",
        help="'dual' creates core + context collections; 'single' is legacy behavior",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete and recreate collection(s) before ingesting",
    )
    parser.add_argument(
        "--jsonl",
        type=Path,
        default=DEFAULT_FOCUSED_JSONL,
        help=f"Path to JSONL file (single mode only, default: {DEFAULT_FOCUSED_JSONL.name})",
    )
    parser.add_argument(
        "--collection",
        type=str,
        default=COLLECTION_FULL,
        help=f"Collection name (single mode only, default: {COLLECTION_FULL})",
    )
    parser.add_argument(
        "--db-dir",
        type=Path,
        default=DEFAULT_DB_DIR,
        help=f"ChromaDB persistent directory (default: {DEFAULT_DB_DIR})",
    )
    args = parser.parse_args()

    if args.mode == "dual":
        ingest_dual(db_dir=args.db_dir, reset=args.reset)
    else:
        ingest_single(
            jsonl_path=args.jsonl,
            db_dir=args.db_dir,
            collection_name=args.collection,
            reset=args.reset,
        )


if __name__ == "__main__":
    main()
