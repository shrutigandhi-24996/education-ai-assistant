from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.app import db
from backend.app.config import settings
from backend.app.pipeline.edu_orchestrator import EduOrchestrator

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"

EDUCATION_MODE = settings.use_education_mode()

app = FastAPI(
    title="Innovative Educational Chatbot" if EDUCATION_MODE else "SRKI Hybrid College Assistant",
    version="0.3.0",
)

# In education mode we use the lightweight LLM+web brain (no local datasets / heavy
# ML), which is also what gets deployed to the cloud. The SRKI pipeline (torch,
# faiss, sentence-transformers) is imported lazily only when needed so the cloud
# build stays small.
if EDUCATION_MODE:
    orchestrator = EduOrchestrator()
else:
    from backend.app.pipeline import web_scraper  # noqa: F401
    from backend.app.pipeline.orchestrator import HybridOrchestrator

    orchestrator = HybridOrchestrator()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    user_id: str = Field(default="anonymous", min_length=1, max_length=256)
    session_id: str = Field(default="default", min_length=1, max_length=128)


class ChatResponse(BaseModel):
    reply: str
    intent: str | None = None
    intents: list[str] | None = None
    is_multi_intent: bool | None = None
    role: str | None = None
    confidence: float | None = None
    needs_clarification: bool = False
    context: dict | None = None
    sources: list[str] | None = None
    source: str | None = None


class HealthResponse(BaseModel):
    status: str
    mode: str
    college: str
    llm_brain_ready: bool = False
    external_search_enabled: bool = False
    multi_intent_enabled: bool = False
    intent_model_ready: bool = False
    rag_ready: bool = False
    curriculum_files: int = 0
    web_scrape_enabled: bool = False
    web_cache_pages: int = 0
    web_cache_fresh: bool = False


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    if EDUCATION_MODE:
        return HealthResponse(
            status="ok",
            mode="education",
            college="ANY",
            llm_brain_ready=orchestrator.ready,
            external_search_enabled=settings.external_search_enabled,
            multi_intent_enabled=True,
        )
    return HealthResponse(
        status="ok",
        mode="srki",
        college=settings.active_college,
        intent_model_ready=orchestrator.intent_model.ready,
        rag_ready=orchestrator.retriever.ready,
        curriculum_files=len(orchestrator.curriculum.entries),
        web_scrape_enabled=settings.web_scrape_enabled,
        web_cache_pages=orchestrator.web.page_count,
        web_cache_fresh=web_scraper.cache_is_fresh(),
        multi_intent_enabled=settings.multi_intent_enabled,
        external_search_enabled=settings.external_search_enabled,
        llm_brain_ready=False,
    )


@app.post("/api/web/refresh")
def refresh_web_cache() -> dict:
    """Re-scrape official SRKI pages into local cache (SRKI mode only)."""
    if EDUCATION_MODE:
        return {"ok": False, "message": "Not applicable in education mode (live web search is used)."}
    if not settings.web_scrape_enabled:
        return {"ok": False, "message": "Web scraping is disabled in config."}
    count = web_scraper.refresh_cache_if_needed(force=True)
    orchestrator.web._pages = web_scraper.load_cache()
    orchestrator.web._loaded = True
    return {"ok": True, "pages_indexed": count}


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    result = orchestrator.chat(req.session_id, req.message)
    db.log_conversation(req.user_id, req.session_id, req.message, result)
    return ChatResponse(**result)


@app.get("/api/conversations")
def conversations(limit: int = 100) -> dict:
    """Recent logged conversation turns (powers the live DB viewer)."""
    limit = max(1, min(limit, 500))
    return {"count": db.count(), "rows": db.recent(limit)}


@app.get("/api/conversations/export")
def export_conversations(fmt: str = "xlsx") -> Response:
    """Download all conversations as Excel (.xlsx), CSV, or PDF."""
    fmt = fmt.lower().strip()
    if fmt in ("xlsx", "excel"):
        data = db.export_xlsx_bytes()
        media = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = "conversations.xlsx"
    elif fmt == "pdf":
        data = db.export_pdf_bytes()
        media = "application/pdf"
        name = "conversations.pdf"
    else:
        data = db.export_csv_bytes()
        media = "text/csv"
        name = "conversations.csv"
    return Response(
        content=data,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@app.delete("/api/conversations")
def clear_conversations() -> dict:
    """Clear all logged conversations (admin refresh after optional export)."""
    removed = db.clear_all()
    return {"ok": True, "removed": removed}


db.init_db()


if FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND), name="static")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND / "index.html")

    @app.get("/admin")
    def admin() -> FileResponse:
        return FileResponse(FRONTEND / "admin.html")
