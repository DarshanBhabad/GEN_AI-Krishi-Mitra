from collections import Counter
import math
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.ai import ai_service
from app.services.vector_store import vector_store


TOKEN_PATTERN = re.compile(r"[\w\u0900-\u097f]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.casefold() for token in TOKEN_PATTERN.findall(text) if len(token) > 1]


def retrieve(db: Session, question: str, limit: int = 5) -> list[dict]:
    rows = db.execute(
        select(KnowledgeChunk, KnowledgeDocument)
        .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
        .where(KnowledgeDocument.approved.is_(True))
    ).all()
    if not rows:
        return []

    query_tokens = tokenize(question)
    if not query_tokens:
        return []
    document_frequency: Counter[str] = Counter()
    tokenized: list[tuple[KnowledgeChunk, KnowledgeDocument, list[str]]] = []
    for chunk, document in rows:
        tokens = tokenize(chunk.content)
        tokenized.append((chunk, document, tokens))
        document_frequency.update(set(tokens))

    count = len(tokenized)
    lexical: dict[str, float] = {}
    query_set = set(query_tokens)
    coverage: dict[str, float] = {}
    for chunk, _, tokens in tokenized:
        frequencies = Counter(tokens)
        score = 0.0
        for term in query_set:
            if frequencies[term]:
                idf = math.log(1 + (count - document_frequency[term] + 0.5) / (document_frequency[term] + 0.5))
                score += idf * frequencies[term] / (frequencies[term] + 1.2)
        lexical[chunk.id] = score
        coverage[chunk.id] = len(query_set.intersection(tokens)) / len(query_set)

    vector_hits: list[tuple[str, float]] = []
    if ai_service.embeddings_ready and vector_store.ready:
        vector_hits = vector_store.search(ai_service.embed([question])[0], limit=max(limit * 3, 10))
    lexical_ranked = sorted(lexical, key=lexical.get, reverse=True)
    vector_ranked = [chunk_id for chunk_id, _ in vector_hits]
    fused: Counter[str] = Counter()
    for ranking in (lexical_ranked, vector_ranked):
        for rank, chunk_id in enumerate(ranking, start=1):
            fused[chunk_id] += 1 / (60 + rank)

    chunks_by_id = {chunk.id: (chunk, doc) for chunk, doc, _ in tokenized}
    ordered_ids = sorted(fused, key=fused.get, reverse=True)
    if not vector_ranked:
        ordered_ids = lexical_ranked
    results = []
    for chunk_id in ordered_ids[:limit]:
        if chunk_id not in chunks_by_id:
            continue
        chunk, document = chunks_by_id[chunk_id]
        results.append(
            {
                "chunk_id": chunk.id,
                "content": chunk.content,
                "coverage": coverage.get(chunk.id, 0.0),
                "approved": document.approved,
                "document_id": document.id,
                "title": document.title,
                "source": document.source,
                "filename": document.filename,
                "published_at": document.published_at,
                "language": document.language,
                "is_demo": document.is_demo,
            }
        )
    return results
