import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import PROJECT_ROOT, settings
from app.core.database import Base, SessionLocal, engine
from app.models import KnowledgeDocument
from app.services.documents import DocumentInput, create_document


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


def seed_demo_knowledge() -> None:
    sample_file = PROJECT_ROOT / "data" / "sample_documents" / "demo_welcome.txt"
    if not sample_file.exists():
        logger.warning("Demo knowledge file was not found at %s", sample_file)
        return
    with SessionLocal() as db:
        if db.query(KnowledgeDocument).filter_by(is_demo=True).first():
            return
        create_document(
            db,
            DocumentInput(
                title="Demonstration knowledge-base notice",
                source="Project demonstration content — not an official agricultural source",
                filename=sample_file.name,
                text=sample_file.read_text(encoding="utf-8"),
                language="hi,mr,en",
                approved=True,
                is_demo=True,
            ),
        )
        logger.info("Seeded clearly labeled demonstration content.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    seed_demo_knowledge()
    if settings.admin_token is None:
        logger.warning("ADMIN_TOKEN is unset; document admin routes are open for local development.")
    if settings.effective_demo_mode:
        logger.info("Running in demo mode; set API_KEY, BASE_URL, MODEL_ID and DEMO_MODE=false for model answers.")
    yield


app = FastAPI(
    title="Krishi Mitra — Voice-First Multilingual Agricultural Assistant",
    description=(
        "Safety-first Hindi and Marathi agricultural information assistant. "
        "Answers require approved evidence; demo content is clearly labeled."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def unexpected_error_handler(_: Request, error: Exception) -> JSONResponse:
    logger.exception("Unhandled API error", exc_info=error)
    return JSONResponse(status_code=500, content={"detail": "Unexpected server error; see server logs."})
