from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from config import CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL

logger = logging.getLogger(__name__)

EXCLUDED_CATEGORIES_FOR_DIETARY_LIST: frozenset[str] = frozenset({
    "salad bar", "dessert", "bread & pastries", "bread", "soups",
    "dressing", "sauce", "bakery", "beverage", "condiment",
})

MEAT_TERMS_FOR_SORT: frozenset[str] = frozenset({
    "beef", "chicken", "turkey", "lamb", "kofta", "fajita", "steak",
    "meat", "sausage", "fish", "salmon", "shrimp", "pork", "duck",
})

_LIST_QUERY_PATTERNS: tuple[str, ...] = (
    "what is", "what are", "show me", "list", " any ", " all ",
    "options", "available", "tonight", "today", "for dinner",
    "for brunch", "for breakfast", "for lunch", "what can i eat",
    "whats halal", "what's halal", "whats vegan", "what's vegan",
)


@dataclass(frozen=True)
class MenuDocument:
    page_content: str
    metadata: dict[str, Any]


class InMemoryMenuStore:
    """Small retrieval-compatible store used when ChromaDB is unavailable."""

    def __init__(self, docs: list[MenuDocument]):
        self.docs = list(docs)

    def similarity_search(
        self,
        query: str,
        k: int = 8,
        filter: dict[str, Any] | None = None,
    ) -> list[MenuDocument]:
        candidates = [doc for doc in self.docs if _matches_filter(doc.metadata, filter)]
        query_terms = _terms(query)

        def score(doc: MenuDocument) -> tuple[int, int]:
            haystack = _terms(doc.page_content)
            overlap = len(query_terms & haystack)
            short_name = str(doc.metadata.get("short_name", "")).lower()
            phrase_bonus = 5 if short_name and short_name in query.lower() else 0
            return overlap + phrase_bonus, -self.docs.index(doc)

        return sorted(candidates, key=score, reverse=True)[:k]

    def get(
        self,
        limit: int = 1,
        include: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> dict[str, list[Any]]:
        candidates = [doc for doc in self.docs if _matches_filter(doc.metadata, where)]
        selected = candidates[:limit]
        result: dict[str, list[Any]] = {}
        include = include or ["metadatas", "documents"]
        if "metadatas" in include:
            result["metadatas"] = [doc.metadata for doc in selected]
        if "documents" in include:
            result["documents"] = [doc.page_content for doc in selected]
        return result

    def persist(self) -> None:
        return None


def extract_filters(query: str) -> dict[str, Any] | None:
    """Extract structured filters from user query before RAG retrieval."""
    filters: dict[str, Any] = {}
    q = query.lower()

    hall_map = {
        "crossroads": "Crossroads",
        "cross roads": "Crossroads",
        "café 3": "Cafe 3",
        "cafe 3": "Cafe 3",
        "cafe three": "Cafe 3",
        "cafe3": "Cafe 3",
        "ckc": "Clark Kerr",
        "clark kerr campus": "Clark Kerr",
        "clark kerr": "Clark Kerr",
        "clark": "Clark Kerr",
        "foothills": "Foothill",
        "foothill": "Foothill",
    }
    for key, val in hall_map.items():
        if key in q:
            filters["dining_hall"] = val
            break

    if "halal" in q:
        filters["halal_status"] = "HALAL"
    if "vegan" in q:
        filters["is_vegan"] = True
    if "vegetarian" in q or "veggie" in q:
        filters["is_vegetarian"] = True

    if "breakfast" in q or "brunch" in q:
        filters["meal_period"] = "Brunch"
    elif "lunch" in q:
        filters["meal_period"] = "Lunch"
    elif "dinner" in q or "tonight" in q:
        filters["meal_period"] = "Dinner"

    return filters if filters else None


def is_list_query(query: str) -> bool:
    """True when the query is asking for a list of items rather than a specific question."""
    q = query.lower()
    return any(pattern in q for pattern in _LIST_QUERY_PATTERNS)


def _get_by_filter(db: Any, filters: dict[str, Any] | None, limit: int = 50) -> list[Any]:
    """Fetch documents by metadata filter without semantic ranking."""
    chroma_filter = vector_filter(filters) if filters else None
    if isinstance(db, InMemoryMenuStore):
        result = db.get(limit=limit, include=["metadatas", "documents"], where=chroma_filter)
    else:
        result = db.get(where=chroma_filter, limit=limit, include=["metadatas", "documents"])
    documents = result.get("documents") or []
    metadatas = result.get("metadatas") or []
    return [
        MenuDocument(page_content=str(doc), metadata=dict(meta or {}))
        for doc, meta in zip(documents, metadatas, strict=False)
    ]


def _is_excluded_for_dietary_list(doc: Any) -> bool:
    meta = doc.metadata if hasattr(doc, "metadata") else {}
    category = str(meta.get("category", "")).lower().strip()
    name = str(meta.get("short_name", "")).lower().strip()
    return category in EXCLUDED_CATEGORIES_FOR_DIETARY_LIST or any(
        excl in name for excl in EXCLUDED_CATEGORIES_FOR_DIETARY_LIST
    )


def _item_sort_key(doc: Any) -> int:
    meta = doc.metadata if hasattr(doc, "metadata") else {}
    halal_status = meta.get("halal_status", "")
    name = str(meta.get("short_name", "")).lower()
    content = str(getattr(doc, "page_content", "")).lower()
    is_halal = halal_status == "HALAL"
    has_meat = any(term in name or term in content for term in MEAT_TERMS_FOR_SORT)
    is_vegan = bool(meta.get("is_vegan", False))
    is_vegetarian = bool(meta.get("is_vegetarian", False))
    if is_halal and has_meat:
        return 0
    if is_vegan or is_vegetarian:
        return 1
    return 2


def sort_and_filter_chunks(chunks: list[Any], has_dietary_filters: bool) -> list[Any]:
    if has_dietary_filters:
        chunks = [c for c in chunks if not _is_excluded_for_dietary_list(c)]
    return sorted(chunks, key=_item_sort_key)


def embed_menu(
    classified_items: list[dict[str, Any]],
    embeddings: Any | None = None,
    persist_directory: str = CHROMA_PATH,
    collection_name: str = COLLECTION_NAME,
    use_chroma: bool = True,
):
    """Full overwrite embed. Called on startup and after MCP refresh."""
    menu_docs = [build_document(item) for item in classified_items]
    if not use_chroma:
        return InMemoryMenuStore(menu_docs)

    try:
        from langchain_core.documents import Document
        from langchain_community.vectorstores import Chroma
        from langchain_openai import OpenAIEmbeddings
    except ImportError:
        logger.warning("LangChain/ChromaDB packages are unavailable; using in-memory menu store")
        return InMemoryMenuStore(menu_docs)

    if embeddings is None:
        embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)

    docs = [
        Document(page_content=doc.page_content, metadata=_chroma_metadata(doc.metadata))
        for doc in menu_docs
    ]
    try:
        reset_chroma_collection(Chroma, embeddings, persist_directory, collection_name)
        db = Chroma.from_documents(
            docs,
            embeddings,
            persist_directory=persist_directory,
            collection_name=collection_name,
        )
        return db
    except Exception:
        logger.exception("Failed to build Chroma menu store; using in-memory menu store")
        return InMemoryMenuStore(menu_docs)


def reset_chroma_collection(
    chroma_class: Any,
    embeddings: Any,
    persist_directory: str,
    collection_name: str,
) -> None:
    """Remove the previous persisted collection before rebuilding today's menu."""
    try:
        existing = chroma_class(
            collection_name=collection_name,
            embedding_function=embeddings,
            persist_directory=persist_directory,
        )
        existing.delete_collection()
    except Exception:
        logger.debug("No existing Chroma collection to reset", exc_info=True)


def retrieve(db: Any, query: str, n_results: int = 8) -> list[Any]:
    """Smart retrieval: list queries use metadata get(), conversational queries use semantic search."""
    filters = extract_filters(query)

    if is_list_query(query):
        has_dietary = bool(filters and any(
            k in filters for k in ("halal_status", "is_vegan", "is_vegetarian")
        ))
        chunks = _get_by_filter(db, filters, limit=50)
        return sort_and_filter_chunks(chunks, has_dietary)

    # Conversational: strip dietary status filters so item is retrieved regardless of halal_status
    non_dietary = {
        k: v for k, v in (filters or {}).items()
        if k not in ("halal_status", "is_vegan", "is_vegetarian")
    }
    chroma_filter = vector_filter(non_dietary) if non_dietary else None
    return db.similarity_search(query, k=n_results, filter=chroma_filter)


def is_stale(db: Any) -> bool:
    """True if stored menu is from a previous day or empty."""
    try:
        results = db.get(limit=1, include=["metadatas"])
        metadatas = results.get("metadatas") or []
        if not metadatas:
            return True
        return metadatas[0].get("date", "") != str(date.today())
    except Exception:
        logger.exception("Failed to inspect menu freshness")
        return True


def build_document(item: dict[str, Any]) -> MenuDocument:
    metadata = build_metadata(item)
    allergens_present = ", ".join(item.get("allergens_present") or []) or "None"
    shellfish_note = item.get("shellfish_note") or "None"
    serving_size = item.get("serving_size")
    serving_unit = item.get("serving_size_unit") or "oz"
    serving_text = f"{serving_size}{serving_unit}" if serving_size is not None else "Unknown"

    doc = f"""
Item: {item.get('short_name', '')}
Dining Hall: {item.get('dining_hall', '')}
Meal: {item.get('meal_period', '')}
Category: {item.get('category', '')}
Serving Size: {serving_text}
Halal Status: {item.get('halal_status', 'UNCERTAIN')}
Halal Reason: {item.get('halal_reason', '')}
Contains Shellfish: {item.get('contains_shellfish', False)}
Shellfish Note: {shellfish_note}
Allergens: {allergens_present}
Calories: {item.get('calories')} | Protein: {item.get('protein')}g | Fat: {item.get('fat')}g |
Carbs: {item.get('carbs')}g | Fiber: {item.get('fiber')}g | Sodium: {item.get('sodium')}mg
Calories Per Oz: {item.get('calories_per_oz')}
Ingredients: {item.get('ingredients', '')}
""".strip()
    return MenuDocument(page_content=doc, metadata=metadata)


def build_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "date": item.get("date", ""),
        "dining_hall": item.get("dining_hall", ""),
        "meal_period": item.get("meal_period", ""),
        "category": item.get("category", ""),
        "halal_status": item.get("halal_status", "UNCERTAIN"),
        "halal_reason": item.get("halal_reason", ""),
        "is_vegan": bool(item.get("is_vegan", False)),
        "is_vegetarian": bool(item.get("is_vegetarian", False)),
        "contains_shellfish": bool(item.get("contains_shellfish", False)),
        "shellfish_note": item.get("shellfish_note") or "",
        "timestamp": item.get("timestamp") or f"{item.get('date', '')}T00:00:00",
        "short_name": item.get("short_name", ""),
        "ingredients": item.get("ingredients", ""),
        "allergens_present": "|".join(item.get("allergens_present") or []),
        "serving_size_unit": item.get("serving_size_unit") or "oz",
    }
    for field in [
        "calories",
        "serving_size",
        "calories_per_oz",
        "protein",
        "fat",
        "sat_fat",
        "trans_fat",
        "cholesterol",
        "carbs",
        "fiber",
        "sugar",
        "sodium",
    ]:
        if item.get(field) is not None:
            metadata[field] = item[field]
    return metadata


def list_documents(db: Any, limit: int = 1000) -> list[MenuDocument]:
    """Return stored menu documents for deterministic answer generation."""
    if isinstance(db, InMemoryMenuStore):
        return list(db.docs[:limit])
    if not hasattr(db, "get"):
        return []
    results = db.get(limit=limit, include=["metadatas", "documents"])
    documents = results.get("documents") or []
    metadatas = results.get("metadatas") or []
    return [
        MenuDocument(page_content=str(page_content), metadata=dict(metadata or {}))
        for page_content, metadata in zip(documents, metadatas, strict=False)
    ]


def _matches_filter(metadata: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    if not filters:
        return True
    if "$and" in filters:
        return all(_matches_filter(metadata, child_filter) for child_filter in filters["$and"])
    return all(metadata.get(key) == value for key, value in filters.items())


def vector_filter(filters: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return a Chroma-compatible filter while keeping the in-memory store compatible."""
    if not filters or len(filters) <= 1:
        return filters
    return {"$and": [{key: value} for key, value in filters.items()]}


def _terms(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _chroma_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Chroma only accepts primitive, non-null metadata values."""
    return {
        key: value
        for key, value in metadata.items()
        if isinstance(value, str | int | float | bool)
    }
