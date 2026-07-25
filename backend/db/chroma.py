import json

import chromadb
import structlog
from chromadb.config import Settings
from chromadb.utils.embedding_functions import (
    DefaultEmbeddingFunction,
    OllamaEmbeddingFunction,
)

from backend.config import (
    EMBEDDING_PROVIDER,
    OLLAMA_BASE_URL,
    OLLAMA_EMBED_MODEL,
    VECTOR_DIR,
)
from backend.db.schema import get_all_semantic_units

log = structlog.get_logger()

_client: chromadb.ClientAPI | None = None
_embedder = None
_semantic_index_ready = False


def get_chroma_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=str(VECTOR_DIR),
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_embedder():
    global _embedder
    if _embedder is not None:
        return _embedder

    if EMBEDDING_PROVIDER == "ollama":
        _embedder = OllamaEmbeddingFunction(
            url=OLLAMA_BASE_URL,
            model_name=OLLAMA_EMBED_MODEL,
        )
    else:
        _embedder = DefaultEmbeddingFunction()

    return _embedder


def get_memories_collection() -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="memories",
        metadata={"hnsw:space": "cosine"},
    )


def get_insights_collection() -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name="insights",
        metadata={"hnsw:space": "cosine"},
    )


def _semantic_collection_name() -> str:
    return f"semantic_units_{EMBEDDING_PROVIDER}"


def get_semantic_units_collection() -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=_semantic_collection_name(),
        metadata={"hnsw:space": "cosine", "embedding_provider": EMBEDDING_PROVIDER},
        embedding_function=_get_embedder(),
    )


def _unit_metadata(unit: dict) -> dict:
    domains = unit.get("domains", "[]")
    if isinstance(domains, str):
        try:
            parsed_domains = json.loads(domains)
        except json.JSONDecodeError:
            parsed_domains = []
    else:
        parsed_domains = domains or []

    return {
        "unit_type": unit.get("unit_type") or "",
        "diary_entry_id": unit.get("diary_entry_id") or 0,
        "life_period": unit.get("life_period") or "unspecified",
        "emotional_valence": unit.get("emotional_valence") or "neutral",
        "domains": ",".join(parsed_domains),
        "insight_potential": unit.get("insight_potential") or "low",
    }


def _ensure_semantic_index() -> None:
    global _semantic_index_ready
    if _semantic_index_ready:
        return

    collection = get_semantic_units_collection()
    if collection.count() == 0:
        units = get_all_semantic_units()
        if units:
            collection.add(
                ids=[f"unit_{unit['id']}" for unit in units],
                documents=[unit.get("content", "") for unit in units],
                metadatas=[_unit_metadata(unit) for unit in units],
            )
            log.info(
                "semantic_index_rebuilt",
                provider=EMBEDDING_PROVIDER,
                units=len(units),
            )
    _semantic_index_ready = True


def ingest_semantic_unit(
    unit_id: int,
    content: str,
    metadata: dict,
) -> str:
    """Add semantic unit to Chroma, return chroma_id."""
    _ensure_semantic_index()
    collection = get_semantic_units_collection()
    chroma_id = f"unit_{unit_id}"
    collection.add(
        ids=[chroma_id],
        documents=[content],
        metadatas=[metadata],
    )
    return chroma_id


def query_semantic_units(
    query_text: str,
    n_results: int = 5,
    filter_dict: dict | None = None,
) -> list[dict]:
    """Retrieve top-k semantic units relevant to query."""
    try:
        _ensure_semantic_index()
        collection = get_semantic_units_collection()
        results = collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=filter_dict,
        )
    except Exception as exc:
        log.warning(
            "semantic_query_failed",
            provider=EMBEDDING_PROVIDER,
            error=str(exc),
        )
        return []

    units = []
    if results and results.get("documents"):
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results.get("metadatas") else []
        ids = results["ids"][0] if results.get("ids") else []
        distances = results["distances"][0] if results.get("distances") else []
        for i, doc in enumerate(docs):
            unit = {
                "chroma_id": ids[i] if i < len(ids) else None,
                "content": doc,
                "distance": distances[i] if i < len(distances) else None,
            }
            if i < len(metas) and metas[i]:
                unit.update(metas[i])
            units.append(unit)
    return units
