from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import re
from uuid import uuid4

import pymupdf
from PIL import Image
import pytesseract
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import KnowledgeChunk, KnowledgeDocument
from app.services.ai import ai_service
from app.services.vector_store import vector_store


MAX_CHUNK_CHARS = 1200
CHUNK_OVERLAP = 160


@dataclass(frozen=True)
class DocumentInput:
    title: str
    source: str
    filename: str
    text: str
    language: str = "unknown"
    published_at: str | None = None
    crop: str | None = None
    region: str | None = None
    approved: bool = False
    is_demo: bool = False


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_pdf_text(data: bytes) -> str:
    with pymupdf.open(stream=data, filetype="pdf") as document:
        pages = []
        for page in document:
            page_text = page.get_text("text").strip()
            if not page_text:
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5), alpha=False)
                image = Image.open(BytesIO(pixmap.tobytes("png")))
                try:
                    page_text = pytesseract.image_to_string(image, lang="hin+mar+eng")
                except pytesseract.TesseractNotFoundError as error:
                    raise RuntimeError(
                        "This PDF needs OCR. Install Tesseract and Hindi/Marathi language data."
                    ) from error
                except pytesseract.TesseractError as error:
                    raise RuntimeError(
                        "OCR failed. Check that Tesseract Hindi and Marathi language data are installed."
                    ) from error
            pages.append(page_text)
        text = "\n".join(pages)
    return clean_text(text)


def chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    clean = clean_text(text)
    if not clean:
        return []
    paragraphs = [part.strip() for part in clean.split("\n") if part.strip()]
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + max_chars, len(paragraph))
                chunks.append(paragraph[start:end])
                if end == len(paragraph):
                    break
                start = end - CHUNK_OVERLAP
            continue
        proposed = f"{current}\n{paragraph}" if current else paragraph
        if len(proposed) > max_chars and current:
            chunks.append(current)
            current = paragraph
        else:
            current = proposed
    if current:
        chunks.append(current)
    return chunks


def create_document(db: Session, item: DocumentInput) -> KnowledgeDocument:
    content = clean_text(item.text)
    chunks = chunk_text(content)
    if not chunks:
        raise ValueError("No readable text was found in the document.")
    document = KnowledgeDocument(
        title=item.title[:300],
        source=item.source[:500],
        filename=Path(item.filename).name[:255],
        language=item.language[:16],
        published_at=item.published_at,
        crop=item.crop,
        region=item.region,
        approved=item.approved,
        is_demo=item.is_demo,
    )
    db.add(document)
    db.flush()
    records = [
        KnowledgeChunk(id=str(uuid4()), document_id=document.id, ordinal=index, content=text)
        for index, text in enumerate(chunks)
    ]
    db.add_all(records)
    db.commit()
    db.refresh(document)

    if item.approved and not item.is_demo and ai_service.embeddings_ready and vector_store.ready:
        vectors = ai_service.embed([record.content for record in records])
        vector_store.upsert(
            [(record.id, vector, {"document_id": document.id}) for record, vector in zip(records, vectors)]
        )
    return document


def approve_document(db: Session, document: KnowledgeDocument) -> KnowledgeDocument:
    document.approved = True
    db.commit()
    db.refresh(document)
    records = list(
        db.scalars(
            select(KnowledgeChunk)
            .where(KnowledgeChunk.document_id == document.id)
            .order_by(KnowledgeChunk.ordinal)
        )
    )
    if records and ai_service.embeddings_ready and vector_store.ready:
        vectors = ai_service.embed([record.content for record in records])
        vector_store.upsert(
            [(record.id, vector, {"document_id": document.id}) for record, vector in zip(records, vectors)]
        )
    return document
