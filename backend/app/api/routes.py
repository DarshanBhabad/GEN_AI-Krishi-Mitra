import base64
import hmac
import logging
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import get_db
from app.models import ChatMessage, ChatSession, KnowledgeDocument
from app.services.ai import AIUnavailableError, ai_service
from app.services.documents import DocumentInput, approve_document, create_document, extract_pdf_text
from app.services.language import detect_language
from app.services.live_data import (
    format_mandi,
    format_weather,
    mandi_prices,
    weather_for_location,
)
from app.services.retrieval import retrieve
from app.services.safety import decide, refusal_text
from app.services.understanding import classify_question
from app.services.voice import voice_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    question: str = Field(min_length=2, max_length=4000)
    language: Literal["hi", "mr"] = "hi"
    session_id: str | None = None
    location: str | None = Field(default=None, max_length=200)


class SourceReference(BaseModel):
    document_id: str
    title: str
    source: str
    reference: str
    published_at: str | None
    is_demo: bool


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    verification: Literal["verified", "uncertain", "unavailable", "demo"]
    reason: str
    intent: str
    language: Literal["hi", "mr"]
    entities: dict[str, str | None]
    sources: list[SourceReference] = Field(default_factory=list)
    live_data: dict | None = None
    transcript: str | None = None
    audio_base64: str | None = None
    audio_mime: str | None = None


class DocumentResponse(BaseModel):
    id: str
    title: str
    source: str
    filename: str
    language: str
    published_at: str | None
    crop: str | None
    region: str | None
    approved: bool
    is_demo: bool
    chunk_count: int


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)


class SpeechResponse(BaseModel):
    audio_base64: str
    audio_mime: str


def _session_for_request(db: Session, session_id: str | None, language: str) -> ChatSession:
    if session_id:
        session = db.get(ChatSession, session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found.")
        session.language = language
        return session
    session = ChatSession(id=str(uuid4()), language=language)
    db.add(session)
    db.flush()
    return session


def _save_message(
    db: Session,
    session: ChatSession,
    role: str,
    content: str,
    verification: str,
    sources: list[dict] | None = None,
) -> None:
    db.add(
        ChatMessage(
            session_id=session.id,
            role=role,
            content=content,
            verification=verification,
            sources=sources or [],
        )
    )


def _sources(retrieved: list[dict]) -> list[SourceReference]:
    sources = {}
    for item in retrieved:
        sources[item["document_id"]] = SourceReference(
            document_id=item["document_id"],
            title=item["title"],
            source=item["source"],
            reference=item["filename"],
            published_at=item["published_at"],
            is_demo=item["is_demo"],
        )
    return list(sources.values())


def _unsupported_live_message(language: str, category: str) -> str:
    if category == "weather":
        return (
            "इस स्थान के लिए अभी मौसम जानकारी प्राप्त नहीं हो सकी। कृपया थोड़ी देर बाद प्रयास करें या आधिकारिक मौसम सेवा देखें।"
            if language == "hi"
            else "या ठिकाणासाठी हवामान माहिती मिळाली नाही. कृपया पुन्हा प्रयत्न करा किंवा अधिकृत हवामान सेवा तपासा."
        )
    return (
        "अभी इस फसल और मंडी के लिए ताज़ा भाव उपलब्ध नहीं हैं। कृपया Agmarknet या e-NAM पर जाँचें।"
        if language == "hi"
        else "या पिकासाठी ताजे बाजारभाव उपलब्ध नाहीत. कृपया Agmarknet किंवा e-NAM वर तपासा."
    )


def _follow_up_text(field: str, language: str) -> str:
    if language == "mr":
        if field == "location":
            return "कृपया तुमचे गाव किंवा जिल्हा सांगा."
        return "कृपया पिकाचे नाव सांगा."
    if field == "location":
        return "कृपया अपने गाँव या जिले का नाम बताइए।"
    if field == "commodity":
        return "कृपया फसल/वस्तु का नाम बताइए।"
    return "कृपया फसल का नाम बताइए।"


async def _answer(
    db: Session,
    question: str,
    language: str,
    location: str | None,
    session_id: str | None,
    transcript: str | None = None,
) -> ChatResponse:
    session = _session_for_request(db, session_id, language)
    _save_message(db, session, "user", question, "unavailable")

    detected = detect_language(question, language)
    context = classify_question(question, location)
    retrieved: list[dict] = []
    live_data = None

    if context.unsafe_chemical:
        decision = decide(context, retrieved)
        answer = refusal_text(decision.reason, detected)
        verification = "unavailable"
        reason = decision.reason
    elif context.needs_follow_up:
        answer = _follow_up_text(context.needs_follow_up, detected)
        verification = "uncertain"
        reason = "missing_required_detail"
    elif context.intent == "weather":
        try:
            live_data = await weather_for_location(context.location or "")
            answer = format_weather(live_data, detected)
            verification = "verified"
            reason = "live_data_retrieved"
        except Exception as error:
            logger.warning("Weather lookup unavailable: %s", type(error).__name__)
            answer = _unsupported_live_message(detected, "weather")
            verification = "unavailable"
            reason = "live_data_unavailable"
    elif context.intent == "mandi":
        if not context.commodity:
            answer = (
                "कृपया फसल/वस्तु का नाम बताइए।"
                if detected == "hi"
                else "कृपया पीक/वस्तूचे नाव सांगा."
            )
            verification = "uncertain"
            reason = "missing_required_detail"
        else:
            try:
                live_data = await mandi_prices(context.commodity, context.market)
                answer = format_mandi(live_data, detected)
                verification = "verified"
                reason = "live_data_retrieved"
            except Exception as error:
                logger.warning("Mandi lookup unavailable: %s", type(error).__name__)
                answer = _unsupported_live_message(detected, "mandi")
                verification = "unavailable"
                reason = "live_data_unavailable"
    else:
        retrieved = retrieve(db, question)
        decision = decide(context, retrieved)
        if not decision.allowed:
            answer = refusal_text(decision.reason, detected)
            verification = "unavailable"
            reason = decision.reason
        elif settings.effective_demo_mode:
            answer = (
                "डेमो मोड: उपलब्ध नमूना दस्तावेज़ आधिकारिक कृषि सलाह नहीं है, इसलिए मैं खेती संबंधी तथ्यात्मक उत्तर नहीं दूँगा। "
                "कृपया स्वीकृत आधिकारिक दस्तावेज़ जोड़ें या KVK से संपर्क करें।"
                if detected == "hi"
                else "डेमो मोड: उपलब्ध नमुना दस्तऐवज अधिकृत कृषी सल्ला नाही; म्हणून मी शेतीविषयक तथ्यात्मक उत्तर देणार नाही. "
                "कृपया मंजूर अधिकृत दस्तऐवज जोडा किंवा KVK शी संपर्क साधा."
            )
            verification = "demo"
            reason = "demo_mode_no_verified_advisory"
        else:
            evidence = [item["content"] for item in retrieved if item["approved"] and not item["is_demo"]]
            if not evidence:
                answer = refusal_text("insufficient_approved_evidence", detected)
                verification = "unavailable"
                reason = "no_non_demo_approved_evidence"
            else:
                try:
                    answer = ai_service.answer(question, detected, evidence)
                    verification = "verified"
                    reason = "answer_grounded_in_approved_documents"
                except Exception as error:
                    logger.exception("Grounded answer generation failed")
                    answer = refusal_text("insufficient_approved_evidence", detected)
                    verification = "unavailable"
                    reason = f"answer_generation_failed:{type(error).__name__}"

    source_references = [source.model_dump() for source in _sources(retrieved)]
    _save_message(db, session, "assistant", answer, verification, source_references)
    db.commit()
    return ChatResponse(
        session_id=session.id,
        answer=answer,
        verification=verification,
        reason=reason,
        intent=context.intent,
        language=detected,
        entities={
            "crop": context.crop,
            "location": context.location,
            "season": context.season,
            "commodity": context.commodity,
            "market": context.market,
        },
        sources=_sources(retrieved),
        live_data=live_data,
        transcript=transcript,
    )


def _require_admin(authorization: str | None = Header(default=None)) -> None:
    if not settings.admin_token:
        return
    expected = f"Bearer {settings.admin_token}"
    if authorization is None or not hmac.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Administrator authorization required.")


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db)) -> ChatResponse:
    return await _answer(
        db,
        request.question.strip(),
        request.language,
        request.location,
        request.session_id,
    )


@router.get("/sessions/{session_id}")
def get_chat_history(session_id: str, db: Session = Depends(get_db)) -> dict:
    session = db.scalar(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found.")
    return {
        "session_id": session.id,
        "language": session.language,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
                "verification": message.verification,
                "sources": message.sources,
                "created_at": message.created_at.isoformat(),
            }
            for message in session.messages
        ],
    }


@router.post("/voice", response_model=ChatResponse)
async def voice(
    file: UploadFile = File(...),
    language: Literal["hi", "mr"] = Form("hi"),
    location: str | None = Form(default=None),
    session_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ChatResponse:
    maximum = settings.max_upload_mb * 1024 * 1024
    data = await file.read(maximum + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded audio file is empty.")
    if len(data) > maximum:
        raise HTTPException(status_code=413, detail=f"Audio exceeds the {settings.max_upload_mb} MB limit.")
    try:
        transcript = await voice_service.transcribe(file, data, language)
    except AIUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    result = await _answer(db, transcript, language, location, session_id, transcript=transcript)
    if result.verification in {"verified", "demo"} and settings.has_tts:
        try:
            audio, mime = voice_service.synthesize(result.answer)
            result.audio_base64 = base64.b64encode(audio).decode("ascii")
            result.audio_mime = mime
        except Exception as error:
            logger.exception("Text-to-speech generation failed")
            result.reason = f"{result.reason};tts_failed:{type(error).__name__}"
    return result


@router.post("/speech", response_model=SpeechResponse)
def speech(request: SpeechRequest) -> SpeechResponse:
    if not settings.has_tts:
        raise HTTPException(
            status_code=503,
            detail="Speech synthesis is not configured; set TTS_MODEL_ID and TTS_VOICE.",
        )
    try:
        audio, mime = voice_service.synthesize(request.text)
    except Exception as error:
        logger.exception("Text-to-speech request failed")
        raise HTTPException(status_code=502, detail="Speech synthesis failed; see server logs.") from error
    return SpeechResponse(audio_base64=base64.b64encode(audio).decode("ascii"), audio_mime=mime)


@router.post("/documents/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    source: str = Form(..., min_length=2, max_length=500),
    language: str = Form(default="unknown", max_length=16),
    published_at: str | None = Form(default=None, max_length=64),
    crop: str | None = Form(default=None, max_length=200),
    region: str | None = Form(default=None, max_length=200),
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()
    if suffix not in {".txt", ".md", ".pdf"}:
        raise HTTPException(status_code=415, detail="Only TXT, Markdown, and PDF documents are supported.")
    maximum = settings.max_upload_mb * 1024 * 1024
    data = await file.read(maximum + 1)
    if len(data) > maximum:
        raise HTTPException(status_code=413, detail=f"Document exceeds the {settings.max_upload_mb} MB limit.")
    try:
        text = extract_pdf_text(data) if suffix == ".pdf" else data.decode("utf-8-sig")
        document = create_document(
            db,
            DocumentInput(
                title=Path(filename).stem,
                source=source,
                filename=filename,
                text=text,
                language=language,
                published_at=published_at,
                crop=crop,
                region=region,
            ),
        )
    except UnicodeDecodeError as error:
        raise HTTPException(status_code=400, detail="Text documents must be UTF-8 encoded.") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except Exception as error:
        logger.exception("Document ingestion failed")
        raise HTTPException(status_code=500, detail="Document ingestion failed; see server logs.") from error
    return _document_response(document)


def _document_response(document: KnowledgeDocument) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        title=document.title,
        source=document.source,
        filename=document.filename,
        language=document.language,
        published_at=document.published_at,
        crop=document.crop,
        region=document.region,
        approved=document.approved,
        is_demo=document.is_demo,
        chunk_count=len(document.chunks),
    )


@router.get("/documents", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)) -> list[DocumentResponse]:
    documents = db.scalars(
        select(KnowledgeDocument).options(selectinload(KnowledgeDocument.chunks)).order_by(KnowledgeDocument.created_at.desc())
    ).all()
    return [_document_response(document) for document in documents]


@router.post("/documents/{document_id}/approve", response_model=DocumentResponse)
def approve(
    document_id: str,
    _: None = Depends(_require_admin),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = db.get(KnowledgeDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    try:
        document = approve_document(db, document)
    except Exception as error:
        logger.exception("Document approval/indexing failed")
        raise HTTPException(status_code=502, detail="Approval or vector indexing failed; see server logs.") from error
    return _document_response(document)


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(select(1))
    except Exception as error:
        logger.exception("Health check database query failed")
        raise HTTPException(status_code=503, detail="Database is unavailable.") from error
    return {"status": "ok", "database": "ok", "mode": "demo" if settings.effective_demo_mode else "live"}


@router.get("/config")
def public_config() -> dict:
    return settings.public_capabilities()


@router.post("/evaluation/run")
def evaluation(db: Session = Depends(get_db)) -> dict:
    from app.services.evaluation import run_evaluation

    return run_evaluation(db)
