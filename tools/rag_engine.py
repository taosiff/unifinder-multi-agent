"""
tools/rag_engine.py - Document Processing, Vector Indexing, and Corrective RAG (CRAG)
Supports PDF, DOCX, and TXT upload for Academic Transcripts, CVs, SOPs, and Program Brochures.
Implements document relevance grading and knowledge fallback.
"""

import os
import re
import math
from typing import List, Dict, Any, Optional
from pathlib import Path
from pypdf import PdfReader

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# In-Memory document store per session: session_id -> list of chunks
# Each chunk: {"doc_name": str, "page": int, "text": str, "vector": dict}
SESSION_DOCUMENT_STORE: Dict[str, List[Dict[str, Any]]] = {}


def extract_text_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text and page numbers from PDF, DOCX, or text files.
    """
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
    else:  # txt, md, etc.
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            pages_data.append({"page": 1, "text": f.read()})

    return pages_data


def chunk_document(pages_data: List[Dict[str, Any]], doc_name: str, chunk_size: int = 400, overlap: int = 80) -> List[Dict[str, Any]]:
    """
    Splits document into overlapping semantic chunks with metadata.
    """
    chunks = []
    chunk_id = 0

    for item in pages_data:
        words = item["text"].split()
        page_num = item["page"]
        
        i = 0
        while i < len(words):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            if len(chunk_text.strip()) > 30:
                chunks.append({
                    "chunk_id": f"{doc_name}_p{page_num}_c{chunk_id}",
                    "doc_name": doc_name,
                    "page": page_num,
                    "text": chunk_text
                })
                chunk_id += 1
            i += (chunk_size - overlap)

    return chunks


def tokenize(text: str) -> List[str]:
    return [w.lower() for w in re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text)]


def compute_bm25_similarity(query_tokens: List[str], doc_tokens: List[str], avg_doc_len: float, k1: float = 1.5, b: float = 0.75) -> float:
    """
    Computes BM25 relevance score between query and chunk tokens.
    """
    if not doc_tokens:
        return 0.0
    doc_len = len(doc_tokens)
    score = 0.0
    doc_freq = {}
    for t in doc_tokens:
        doc_freq[t] = doc_freq.get(t, 0) + 1

    for q in query_tokens:
        if q in doc_freq:
            f = doc_freq[q]
            denom = f + k1 * (1.0 - b + b * (doc_len / (avg_doc_len or 1.0)))
            score += (f * (k1 + 1.0)) / (denom or 1.0)
    return score


def index_user_document(session_id: str, file_path: str, doc_name: str) -> Dict[str, Any]:
    """
    Indexes an uploaded document for a specific session.
    """
    pages = extract_text_from_file(file_path)
    chunks = chunk_document(pages, doc_name)

    if session_id not in SESSION_DOCUMENT_STORE:
        SESSION_DOCUMENT_STORE[session_id] = []

    SESSION_DOCUMENT_STORE[session_id].extend(chunks)

    # Perform quick profile extraction (GPA, degree, major detection)
    profile_hints = extract_profile_from_text("\n".join([p["text"] for p in pages]))

    return {
        "success": True,
        "doc_name": doc_name,
        "total_pages": len(pages),
        "total_chunks": len(chunks),
        "profile_hints": profile_hints
    }


def extract_profile_from_text(text: str) -> Dict[str, Any]:
    """
    Detects CGPA, IELTS, and majors from uploaded transcript or resume text.
    """
    hints = {}

    # GPA detection (e.g. CGPA: 3.65 / 4.0, Cumulative Grade Point Average (CGPA): 3.75, or GPA 3.42)
    gpa_match = re.search(r"(?:cgpa|gpa|grade\s*point\s*average)[^0-9\n\r]*?([0-3]\.\d{1,2}|4\.00?|\b[7-9]\.\d{1,2}\s*/\s*10)", text, re.IGNORECASE)
    if gpa_match:
        val = gpa_match.group(1).replace(" ", "")
        hints["detected_gpa"] = val

    # IELTS detection (e.g. IELTS 7.5, Overall IELTS Band: 7.5, Band Score: 7.0)
    ielts_match = re.search(r"(?:ielts|band\s*score|overall\s*band)[^0-9\n\r]*?([5-9](?:\.[05])?)", text, re.IGNORECASE)
    if ielts_match:
        hints["detected_ielts"] = float(ielts_match.group(1))

    # Major detection
    majors = ["Computer Science", "Software Engineering", "Data Science", "Artificial Intelligence", "Electrical Engineering", "Mechanical Engineering", "Biotechnology", "Business Administration", "Finance", "Civil Engineering"]
    for m in majors:
        if re.search(r"\b" + re.escape(m) + r"\b", text, re.IGNORECASE):
            hints["detected_major"] = m
            break

    return hints


def retrieve_relevant_chunks(session_id: str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
    """
    Retrieves top relevant chunks from student's indexed documents using BM25 scoring.
    """
    chunks = SESSION_DOCUMENT_STORE.get(session_id, [])
    if not chunks:
        return []

    q_tokens = tokenize(query)
    if not q_tokens:
        return chunks[:top_k]

    doc_token_lists = [tokenize(c["text"]) for c in chunks]
    avg_len = sum(len(d) for d in doc_token_lists) / (len(doc_token_lists) or 1.0)

    scored = []
    for i, c in enumerate(chunks):
        score = compute_bm25_similarity(q_tokens, doc_token_lists[i], avg_len)
        scored.append((score, c))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored[:top_k] if item[0] > 0.1] or [scored[0][1]] if scored else []


def grade_document_relevance(chunks: List[Dict[str, Any]], query: str) -> Dict[str, Any]:
    """
    Corrective RAG (CRAG) Evaluator:
    Grades whether the retrieved document chunks contain sufficient signal to answer the query.
    If yes: Status is 'RELEVANT'.
    If partial/low: Status is 'PARTIAL_FALLBACK'.
    If no: Status is 'IRRELEVANT_WEB_SEARCH_REQUIRED'.
    """
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
    """
    Returns list of unique document names uploaded in this session.
    """
    chunks = SESSION_DOCUMENT_STORE.get(session_id, [])
    seen = set()
    result = []
    for c in chunks:
        d = c["doc_name"]
        if d not in seen:
            seen.add(d)
            result.append(d)
    return result
