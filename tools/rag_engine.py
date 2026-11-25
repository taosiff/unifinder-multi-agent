"""
tools/rag_engine.py - Cloud-Database-Backed Document Processing & Corrective RAG (C-RAG)
Supports PDF, DOCX, and TXT upload for Academic Transcripts, CVs, SOPs, and Program Brochures.
Stores extracted chunks and CV profile hints directly in the online PostgreSQL/SQLite database
(no ChromaDB or local vector store needed — ideal for free-tier cloud deployment on Render).
"""

import os
import re
from typing import List, Dict, Any
from pathlib import Path
from pypdf import PdfReader

from database import save_session_document, get_session_document_records, is_postgres

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Fast in-memory session cache (backed by PostgreSQL/SQLite session_documents table)
SESSION_DOCUMENT_STORE: Dict[str, List[Dict[str, Any]]] = {}


def extract_text_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Extracts text and page numbers from PDF, DOCX, or text files."""
    path = Path(file_path)
    ext = path.suffix.lower()
    pages_data = []

    if ext == ".pdf":
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                pages_data.append({"page": i + 1, "text": text.strip()})
    elif ext == ".docx":
        import docx
        doc = docx.Document(file_path)
        full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        pages_data.append({"page": 1, "text": full_text})
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            pages_data.append({"page": 1, "text": f.read()})

    return pages_data


def chunk_document(pages_data: List[Dict[str, Any]], doc_name: str, chunk_size: int = 350, overlap: int = 60) -> List[Dict[str, Any]]:
    """Splits document into overlapping semantic chunks with metadata."""
    chunks = []
    chunk_id = 0

    for item in pages_data:
        words = item["text"].split()
        page_num = item["page"]

        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            if len(chunk_text.strip()) > 25:
                chunks.append({
                    "chunk_id": f"{doc_name}_p{page_num}_c{chunk_id}",
                    "doc_name": doc_name,
                    "page": page_num,
                    "text": chunk_text
                })
                chunk_id += 1
            i += max(1, chunk_size - overlap)

    return chunks


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text)]


def compute_bm25_similarity(query_tokens: List[str], doc_tokens: List[str], avg_doc_len: float, k1: float = 1.5, b: float = 0.75) -> float:
    if not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    score = 0.0
    doc_freq: Dict[str, int] = {}
    for t in doc_tokens:
        doc_freq[t] = doc_freq.get(t, 0) + 1

    for q in query_tokens:
        if q in doc_freq:
            f = doc_freq[q]
            denom = f + k1 * (1.0 - b + b * (doc_len / (avg_doc_len or 1.0)))
            score += (f * (k1 + 1.0)) / (denom or 1.0)
    return score


def extract_profile_from_text(text: str) -> Dict[str, Any]:
    """
    Extracts structured CV/Transcript facts: CGPA, IELTS/TOEFL, Major,
    Recommended Next Degree, and Technical Skills.
    """
    hints: Dict[str, Any] = {}

    gpa_match = re.search(
        r"(?:cgpa|gpa|grade\s*point\s*average)[^0-9\n\r]*?([0-3]\.\d{1,2}|4\.00?|\b[7-9]\.\d{1,2}\s*/\s*10)",
        text,
        re.IGNORECASE
    )
    if gpa_match:
        hints["detected_gpa"] = gpa_match.group(1).replace(" ", "")

    ielts_match = re.search(r"(?:ielts|band\s*score|overall\s*band)[^0-9\n\r]*?([5-9](?:\.[05])?)", text, re.IGNORECASE)
    if ielts_match:
        hints["detected_ielts"] = float(ielts_match.group(1))

    toefl_match = re.search(r"toefl[^0-9\n\r]*?(\d{2,3})", text, re.IGNORECASE)
    if toefl_match:
        hints["detected_toefl"] = int(toefl_match.group(1))

    majors = [
        "Artificial Intelligence", "Machine Learning", "Data Science", "Computer Science",
        "Software Engineering", "Cybersecurity", "Robotics", "Electrical Engineering",
        "Mechanical Engineering", "Biotechnology", "Bioinformatics", "Business Administration",
        "Finance", "Economics", "Civil Engineering", "Public Health", "Environmental Science"
    ]
    for m in majors:
        if re.search(r"\b" + re.escape(m) + r"\b", text, re.IGNORECASE):
            hints["detected_major"] = m
            break

    low = text.lower()
    if any(k in low for k in ("m.sc", "msc", "master of science", "master's degree", "m.tech", "mba")):
        hints["recommended_degree"] = "PhD"
    elif any(k in low for k in ("b.sc", "bsc", "bachelor", "b.tech", "b.e.", "undergraduate")):
        hints["recommended_degree"] = "MSc"
    elif any(k in low for k in ("high school", "a-levels", "ib diploma", "hsc", "12th grade")):
        hints["recommended_degree"] = "BSc"

    skill_vocab = [
        "Python", "PyTorch", "TensorFlow", "Machine Learning", "Deep Learning", "NLP",
        "LangChain", "SQL", "PostgreSQL", "Docker", "Kubernetes", "AWS", "React",
        "Java", "C++", "JavaScript", "TypeScript", "FastAPI", "Data Analysis", "R",
        "MATLAB", "AutoCAD", "SolidWorks", "Finance", "Econometrics"
    ]
    found_skills = [s for s in skill_vocab if re.search(r"\b" + re.escape(s) + r"\b", text, re.IGNORECASE)]
    if found_skills:
        hints["skills"] = found_skills[:10]

    return hints


def _ensure_session_loaded(session_id: str) -> List[Dict[str, Any]]:
    """Loads chunks from memory, or hydrates from online PostgreSQL/SQLite if not cached."""
    if session_id in SESSION_DOCUMENT_STORE and SESSION_DOCUMENT_STORE[session_id]:
        return SESSION_DOCUMENT_STORE[session_id]

    records = get_session_document_records(session_id)
    hydrated: List[Dict[str, Any]] = []
    for rec in records:
        hydrated.extend(rec.get("chunks", []))

    if hydrated:
        SESSION_DOCUMENT_STORE[session_id] = hydrated
    return hydrated


def index_user_document(session_id: str, file_path: str, doc_name: str) -> Dict[str, Any]:
    """
    Extracts text, chunks it, extracts CV profile hints, and persists everything
    directly into the online PostgreSQL/SQLite database (plus short-term memory cache).
    """
    pages = extract_text_from_file(file_path)
    chunks = chunk_document(pages, doc_name)

    if session_id not in SESSION_DOCUMENT_STORE:
        SESSION_DOCUMENT_STORE[session_id] = []
    SESSION_DOCUMENT_STORE[session_id].extend(chunks)

    full_text = "\n".join([p["text"] for p in pages])
    profile_hints = extract_profile_from_text(full_text)

    # Persist to online PostgreSQL / SQLite database
    save_session_document(session_id, doc_name, chunks, profile_hints)

    storage_mode = "PostgreSQL (Online DB)" if is_postgres() else "SQLite (Local DB)"
    return {
        "success": True,
        "doc_name": doc_name,
        "total_pages": len(pages),
        "total_chunks": len(chunks),
        "storage": storage_mode,
        "profile_hints": profile_hints
    }


def retrieve_relevant_chunks(session_id: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """Retrieves top relevant chunks from short-term memory / online database using BM25."""
    chunks = _ensure_session_loaded(session_id)
    if not chunks:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return [{**c, "retrieval_method": "Session DB"} for c in chunks[:top_k]]

    doc_token_lists = [tokenize(c["text"]) for c in chunks]
    avg_len = sum(len(d) for d in doc_token_lists) / (len(doc_token_lists) or 1.0)

    scored = [(compute_bm25_similarity(q_tokens, doc_token_lists[i], avg_len), c) for i, c in enumerate(chunks)]
    scored.sort(key=lambda x: x[0], reverse=True)

    matched = [{**item[1], "retrieval_method": "Online DB + BM25"} for item in scored[:top_k] if item[0] > 0.1]
    if not matched and scored:
        matched = [{**scored[0][1], "retrieval_method": "Online DB Fallback"}]
    return matched


def get_all_session_chunks(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches all stored chunks for a session from memory or online PostgreSQL/SQLite."""
    return _ensure_session_loaded(session_id)[:limit]


def grade_document_relevance(chunks: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """Corrective RAG (CRAG) Evaluator."""
    if not chunks:
        return {
            "status": "IRRELEVANT_WEB_SEARCH_REQUIRED",
            "confidence": 0.0,
            "reason": "No document chunks uploaded or retrieved for this session."
        }

    q_tokens = set(tokenize(query))
    matched_tokens_total = 0

    for c in chunks:
        c_tokens = set(tokenize(c["text"]))
        overlap = q_tokens.intersection(c_tokens)
        matched_tokens_total += len(overlap)

    relevance_ratio = matched_tokens_total / (len(q_tokens) or 1.0)

    if relevance_ratio >= 0.7:
        status = "RELEVANT"
    elif relevance_ratio >= 0.35:
        status = "PARTIAL_FALLBACK"
    else:
        status = "IRRELEVANT_WEB_SEARCH_REQUIRED"

    return {
        "status": status,
        "confidence": min(1.0, round(relevance_ratio, 2)),
        "chunks_count": len(chunks)
    }


def get_session_documents(session_id: str) -> List[str]:
    """Returns list of unique document names uploaded in this session from memory/online DB."""
    chunks = _ensure_session_loaded(session_id)
    seen = set()
    result = []
    for c in chunks:
        d = c["doc_name"]
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result


def clear_session_memory(session_id: str) -> None:
    """Clears in-memory cached document chunks for a session."""
    SESSION_DOCUMENT_STORE.pop(session_id, None)
