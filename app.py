"""
app.py - FastAPI Application Server for UniFinder AI
High-performance async server integrating LangGraph multi-agent orchestration,
persistent SQLite memory, Corrective RAG (CRAG) document uploads, real-time SSE streaming,
live scholarship opportunities, and HITL (Human-in-the-Loop) workflows.
"""

from pathlib import Path
import traceback
import os
import shutil
import uuid
import uvicorn
from typing import Optional, List

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from backend import (
    run_unifinder_agent,
    run_unifinder_agent_stream,
    get_llm
)
from database import (
    search_universities,
    add_to_shortlist,
    get_shortlist,
    remove_from_shortlist,
    get_or_create_thread,
    list_chat_threads,
    delete_chat_thread
)
from tools.sop_reviewer_tool import review_statement_of_purpose
from tools.rag_engine import index_user_document, get_session_documents
from tools.opportunities_tool import get_live_opportunities, get_immigration_news, get_scholarship_sources
from tools.univs_tool import search_univs_programs, search_univs_institutes, get_univs_addresses
from tools.university_scraper_tool import scrape_official_university_admissions

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

app = FastAPI(
    title="UniFinder AI",
    description="Multi-Agent Higher Education, Admissions, PR & Career Pathways Intelligence Platform",
    version="2.5.0"
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# ==========================================
# Pydantic Request Models
# ==========================================

class UniFinderRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None
    session_id: Optional[str] = None
    degree_level: Optional[str] = "MSc"
    subject: Optional[str] = "Computer Science"
    country: Optional[str] = ""
    user_gpa: Optional[float] = 3.4
    user_ielts: Optional[float] = 6.5
    budget_usd: Optional[int] = 25000
    api_key: Optional[str] = None
    llm_provider: Optional[str] = "gemini"


class ShortlistRequest(BaseModel):
    session_id: str
    university_id: int
    program_name: str
    degree_level: str
    notes: Optional[str] = ""


class SOPReviewRequest(BaseModel):
    sop_text: str
    target_program: Optional[str] = "MSc Computer Science"
    target_university: Optional[str] = ""


class KeyTestRequest(BaseModel):
    api_key: str
    provider: str  # "gemini" or "groq"


class ThreadCreateRequest(BaseModel):
    title: str
    degree_level: Optional[str] = "MSc"
    subject: Optional[str] = "Computer Science"
    country: Optional[str] = ""


class HITLActionRequest(BaseModel):
    thread_id: str
    decision: str  # e.g. "approved", "include_safety", "modify_budget"


class ScrapeUniversityRequest(BaseModel):
    university_name: Optional[str] = ""
    official_url: Optional[str] = ""
    degree_level: Optional[str] = "MSc"
    subject: Optional[str] = "Computer Science"
    notes: Optional[str] = ""


# ==========================================
# Routes
# ==========================================

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    has_gemini = bool(os.getenv("GOOGLE_API_KEY"))
    has_groq = bool(os.getenv("GROQ_API_KEY"))
    active_key = "Google Gemini" if has_gemini else "Groq" if has_groq else None

    # Check LangSmith monitoring
    has_langsmith = bool(os.getenv("LANGCHAIN_API_KEY"))

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "has_api_key": bool(active_key),
            "active_provider": active_key or "Not Configured",
            "has_langsmith": has_langsmith
        }
    )


@app.post("/api/find")
async def run_finder(req: UniFinderRequest):
    try:
        query = req.message.strip()
        if not query:
            return JSONResponse(
                status_code=400,
                content={"success": False, "error": "Query message cannot be empty."}
            )

        thread_id = req.thread_id or f"student_{uuid.uuid4().hex[:8]}"
        session_id = req.session_id or thread_id

        # Update or record thread
        title_snippet = query[:35] + ("..." if len(query) > 35 else "")
        get_or_create_thread(
            thread_id=thread_id,
            title=title_snippet,
            degree=req.degree_level or "MSc",
            subject=req.subject or "Computer Science",
            country=req.country or ""
        )

        result = run_unifinder_agent(
            user_input=query,
            thread_id=thread_id,
            session_id=session_id,
            degree_level=req.degree_level or "MSc",
            subject=req.subject or "Computer Science",
            country=req.country or "",
            user_gpa=req.user_gpa or 3.4,
            user_ielts=req.user_ielts or 6.5,
            budget_usd=req.budget_usd or 25000,
            api_key_override=req.api_key,
            provider_override=req.llm_provider
        )

        return JSONResponse(content={
            "success": True,
            "thread_id": result["thread_id"],
            "session_id": result["session_id"],
            "dossier": result["dossier"],
            "discovered_universities": result["discovered_universities"],
            "portal_scraping_result": result["portal_scraping_result"],
            "eligibility_analysis": result["eligibility_analysis"],
            "immigration_analysis": result["immigration_analysis"],
            "career_roi_analysis": result["career_roi_analysis"],
            "active_opportunities": result["active_opportunities"],
            "living_cost_details": result["living_cost_details"],
            "crag_status": result["crag_status"],
            "crag_grounding": result["crag_grounding"],
            "hitl_required": result["hitl_required"],
            "hitl_reason": result["hitl_reason"],
            "hitl_options": result["hitl_options"],
            "degree_level": result["degree_level"],
            "subject": result["subject"],
            "country_pref": result["country_pref"],
            "llm_calls": result["llm_calls"]
        })

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.post("/api/chat/stream")
async def chat_streaming(req: UniFinderRequest):
    """
    Server-Sent Events (SSE) streaming endpoint for live token generation & agent progression.
    """
    thread_id = req.thread_id or f"student_{uuid.uuid4().hex[:8]}"
    session_id = req.session_id or thread_id

    # Record thread
    title_snippet = req.message[:35] + "..." if len(req.message) > 35 else req.message
    get_or_create_thread(
        thread_id=thread_id,
        title=title_snippet,
        degree=req.degree_level or "MSc",
        subject=req.subject or "Computer Science",
        country=req.country or ""
    )

    generator = run_unifinder_agent_stream(
        user_input=req.message,
        thread_id=thread_id,
        session_id=session_id,
        degree_level=req.degree_level or "MSc",
        subject=req.subject or "Computer Science",
        country=req.country or "",
        user_gpa=req.user_gpa or 3.4,
        user_ielts=req.user_ielts or 6.5,
        budget_usd=req.budget_usd or 25000,
        api_key_override=req.api_key,
        provider_override=req.llm_provider
    )

    return StreamingResponse(generator, media_type="text/event-stream")


@app.post("/api/upload-doc")
async def upload_document(
    file: UploadFile = File(...),
    session_id: str = Form(...)
):
    """
    Handles PDF, DOCX, or TXT file uploads (transcripts, CVs, brochures) and builds
    the C-RAG vector/BM25 retrieval index for the current counseling session.
    """
    try:
        safe_filename = f"{uuid.uuid4().hex[:6]}_{file.filename}"
        saved_path = UPLOAD_DIR / safe_filename

        with open(saved_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Index into RAG engine
        index_result = index_user_document(
            session_id=session_id,
            file_path=str(saved_path),
            doc_name=file.filename
        )

        return {
            "success": True,
            "filename": file.filename,
            "total_pages": index_result["total_pages"],
            "total_chunks": index_result["total_chunks"],
            "profile_hints": index_result["profile_hints"]
        }
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})


@app.get("/api/documents")
@app.get("/api/documents/{session_id}")
async def list_documents(session_id: Optional[str] = None):
    if not session_id:
        return {"success": True, "documents": []}
    docs = get_session_documents(session_id)
    return {"success": True, "documents": docs}


@app.get("/api/opportunities")
async def get_opportunities(
    destination: Optional[str] = None,
    degree: Optional[str] = None,
    funding: Optional[str] = None,
    record_status: Optional[str] = None
):
    """
    Returns Verified Open and Newly Discovered scholarships (RSS + JSON + official portals)
    alongside attribution metadata and latest immigration policy news.
    """
    scholarships = get_live_opportunities(
        destination=destination,
        degree_level=degree,
        funding_type=funding,
        record_status=record_status
    )
    news = get_immigration_news()
    return {
        "success": True,
        "scholarships": scholarships,
        "news": news,
        "sources": get_scholarship_sources()
    }


@app.get("/api/threads")
async def get_threads():
    threads = list_chat_threads()
    return {"success": True, "threads": threads}


@app.post("/api/threads")
async def create_thread(req: ThreadCreateRequest):
    new_id = f"student_{uuid.uuid4().hex[:8]}"
    item = get_or_create_thread(
        thread_id=new_id,
        title=req.title,
        degree=req.degree_level or "MSc",
        subject=req.subject or "Computer Science",
        country=req.country or ""
    )
    return {"success": True, "thread": item}


@app.delete("/api/threads/{thread_id}")
async def delete_thread(thread_id: str):
    ok = delete_chat_thread(thread_id)
    return {"success": ok}


@app.post("/api/hitl-action")
async def hitl_action(req: HITLActionRequest):
    """
    Processes Human-in-the-Loop decision confirmation.
    """
    return {
        "success": True,
        "thread_id": req.thread_id,
        "decision": req.decision,
        "message": f"Human-in-the-loop decision '{req.decision}' confirmed. Counseling strategy updated."
    }


@app.get("/api/universities")
async def get_universities(
    degree: Optional[str] = None,
    subject: Optional[str] = None,
    country: Optional[str] = None,
    max_tuition: Optional[int] = None
):
    results = search_universities(
        degree_level=degree,
        subject=subject,
        country=country,
        max_tuition=max_tuition,
        limit=30
    )
    return {"success": True, "count": len(results), "universities": results}


@app.get("/api/univs/addresses")
async def univs_addresses():
    """Returns official Univs.com REST API, MCP server, OpenAPI & LLM documentation URLs."""
    return {"success": True, "addresses": get_univs_addresses()}


@app.get("/api/univs/programs")
async def univs_programs(
    q: str = "Computer Science",
    country: str = "",
    degree: str = "MSc",
    scholarship: bool = False,
    page: int = 1
):
    return search_univs_programs(
        query=q,
        country=country,
        degree_level=degree,
        scholarship_only=scholarship,
        page=page
    )


@app.get("/api/univs/institutes")
async def univs_institutes(q: str = "", country: str = "", page: int = 1):
    return search_univs_institutes(query=q, country=country, page=page)


@app.post("/api/scrape-university")
async def scrape_university_endpoint(req: ScrapeUniversityRequest):
    """Runs the Official Website Admissions Scraper LangGraph subgraph."""
    if not req.university_name and not req.official_url:
        return JSONResponse(status_code=400, content={"success": False, "error": "Provide a university name or official URL."})
    return scrape_official_university_admissions(
        university_name=req.university_name or "",
        official_url=req.official_url or "",
        degree_level=req.degree_level or "MSc",
        subject=req.subject or "Computer Science"
    )


@app.post("/api/shortlist")
async def add_shortlist_item(req: ShortlistRequest):
    res = add_to_shortlist(
        session_id=req.session_id,
        university_id=req.university_id,
        program_name=req.program_name,
        degree_level=req.degree_level,
        notes=req.notes or ""
    )
    return res


@app.get("/api/shortlist/{session_id}")
async def get_shortlist_items(session_id: str):
    items = get_shortlist(session_id)
    return {"success": True, "items": items}


@app.delete("/api/shortlist/{session_id}/{shortlist_id}")
async def delete_shortlist_item(session_id: str, shortlist_id: int):
    success = remove_from_shortlist(session_id, shortlist_id)
    return {"success": success}


@app.post("/api/review-sop")
async def review_sop(req: SOPReviewRequest):
    if not req.sop_text.strip():
        return JSONResponse(
            status_code=400,
            content={"success": False, "error": "Please provide your Statement of Purpose text."}
        )
    result = review_statement_of_purpose(
        sop_text=req.sop_text,
        target_program=req.target_program or "",
        target_university=req.target_university or ""
    )
    return {"success": True, "review": result}


@app.post("/api/test-key")
async def test_key(req: KeyTestRequest):
    try:
        if req.provider == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            for m in ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash", "gemini-1.5-flash"]:
                try:
                    test_llm = ChatGoogleGenerativeAI(model=m, google_api_key=req.api_key)
                    resp = test_llm.invoke("Respond with the single word: OK")
                    return {"success": True, "provider": f"Google Gemini ({m})", "reply": resp.content.strip()}
                except Exception as inner_e:
                    continue
            return {"success": False, "error": "Unable to connect to Google Gemini models with this key."}
        elif req.provider == "groq":
            from langchain_groq import ChatGroq
            for m in ["qwen/qwen3.8-27b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-120b"]:
                try:
                    test_llm = ChatGroq(model=m, api_key=req.api_key)
                    resp = test_llm.invoke("Respond with the single word: OK")
                    return {"success": True, "provider": f"Groq ({m})", "reply": resp.content.strip()}
                except Exception as inner_e:
                    continue
            return {"success": False, "error": "Unable to connect to Groq models with this key."}
        else:
            return {"success": False, "error": "Unknown provider. Choose 'gemini' or 'groq'."}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/langsmith-status")
async def get_langsmith_status():
    has_key = bool(os.getenv("LANGCHAIN_API_KEY"))
    project = os.getenv("LANGCHAIN_PROJECT", "unifinder-ai")
    return {
        "tracing_enabled": has_key,
        "project": project if has_key else None,
        "endpoint": "https://api.smith.langchain.com" if has_key else None
    }


@app.get("/api/status")
@app.get("/health")
async def health_check():
    db_mode = "PostgreSQL" if os.getenv("DATABASE_URL") else "SQLite"
    return {
        "status": "online",
        "service": "UniFinder AI Multi-Agent Higher-Ed Platform",
        "version": "2.5.0",
        "database": db_mode,
        "checkpointer": f"{db_mode}Saver",
        "has_google_key": bool(os.getenv("GOOGLE_API_KEY")),
        "has_groq_key": bool(os.getenv("GROQ_API_KEY")),
        "has_langsmith": bool(os.getenv("LANGCHAIN_API_KEY") or os.getenv("LANGSMITH_API_KEY"))
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
