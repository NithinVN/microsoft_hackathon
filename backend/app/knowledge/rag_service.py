from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List


KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "data" / "runbooks"


def _read_text_documents() -> List[Dict[str, Any]]:
    if not KNOWLEDGE_DIR.exists():
        return []

    documents: List[Dict[str, Any]] = []
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        parts = text.split("\n## ")
        if not parts:
            continue

        title = parts[0].strip().splitlines()[0].replace("# ", "") if parts[0].strip() else path.stem
        sections: List[Dict[str, Any]] = []
        for idx, section in enumerate(parts):
            if idx == 0:
                content = section.strip()
                if content:
                    sections.append({
                        "section_name": "overview",
                        "content": content,
                    })
                continue

            heading, _, rest = section.partition("\n")
            section_name = heading.strip()
            content = rest.strip()
            if content:
                sections.append({
                    "section_name": section_name,
                    "content": content,
                })

        documents.append({
            "document_name": path.name,
            "title": title,
            "path": str(path),
            "sections": sections,
            "raw_text": text,
        })
    return documents


def ingest_runbooks() -> Dict[str, Any]:
    documents = _read_text_documents()
    return {
        "documents": [
            {
                "document_name": doc["document_name"],
                "title": doc["title"],
                "sections": [
                    {
                        "relevant_section": section["section_name"],
                        "retrieved_text": section["content"],
                    }
                    for section in doc["sections"]
                ],
            }
            for doc in documents
        ],
        "total_documents": len(documents),
    }


def _score_relevance(query: str, text: str) -> float:
    query_terms = {token.lower() for token in re.findall(r"[a-zA-Z0-9]+", query) if len(token) > 2}
    if not query_terms:
        return 0.0

    text_terms = {token.lower() for token in re.findall(r"[a-zA-Z0-9]+", text) if len(token) > 2}
    overlap = query_terms & text_terms
    if not overlap:
        return 0.0
    score = len(overlap) / max(1, len(query_terms))
    return round(min(1.0, score * 1.5), 3)


def retrieve_runbook_knowledge(query: str, service: str | None = None, limit: int = 3) -> Dict[str, Any]:
    documents = _read_text_documents()
    if not documents:
        return {
            "documents": [],
            "query": query,
            "service": service,
            "note": "No operational runbook documents were found in the knowledge directory.",
        }

    normalized_query = (query or "").strip().lower()
    service_hint = (service or "").strip().lower()

    matches: List[Dict[str, Any]] = []
    for doc in documents:
        if service_hint and service_hint not in doc["document_name"].lower() and service_hint not in doc["title"].lower() and service_hint not in doc["raw_text"].lower():
            pass

        for section in doc["sections"]:
            section_text = section["content"]
            relevance = _score_relevance(normalized_query, section_text)
            if service_hint:
                if service_hint in doc["document_name"].lower() or service_hint in section_text.lower() or service_hint in doc["title"].lower():
                    relevance = max(relevance, 0.3)
            if normalized_query and relevance <= 0:
                continue
            if not normalized_query:
                relevance = 0.2
            matches.append({
                "document_name": doc["document_name"],
                "relevant_section": section["section_name"],
                "retrieved_text": section_text[:1200],
                "relevance_info": {
                    "query_terms": sorted({token for token in re.findall(r"[a-zA-Z0-9]+", normalized_query) if len(token) > 2}),
                    "score": relevance,
                    "matched_service": service_hint,
                },
            })

    ordered = sorted(matches, key=lambda item: item["relevance_info"]["score"], reverse=True)
    deduped: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in ordered[:limit]:
        key = (item["document_name"], item["relevant_section"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return {
        "documents": deduped,
        "query": query,
        "service": service,
        "total_matches": len(deduped),
    }


__all__ = ["ingest_runbooks", "retrieve_runbook_knowledge"]
