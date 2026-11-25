"""
tools/rag_engine.py - Persistent Vector Store (ChromaDB), Embeddings & Corrective RAG (C-RAG)
Supports PDF, DOCX, and TXT upload for Academic Transcripts, CVs, SOPs, and Program Brochures.
Uses ChromaDB + GoogleGenerativeAIEmbeddings (with NumPy dense vector fallback) + BM25 hybrid retrieval.
"""

import os
import re
import hashlib
from typing import List, Dict, Any, Optional
from pathlib import Path

import numpy as np
import chromadb
from pypdf import PdfReader

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
VECTOR_DB_DIR = os.path.join(BASE_DIR, "vector_store")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(VECTOR_DB_DIR, exist_ok=True)

# Persistent ChromaDB Client & Collection
_CHROMA_CLIENT = chromadb.PersistentClient(path=VECTOR_DB_DIR)
_COLLECTION = _CHROMA_CLIENT.get_or_create_collection(
    name="unifinder_cv_docs",
    metadata={"hnsw:space": "cosine"}
)

# In-memory cache per session for fast BM25 & metadata listing
SESSION_DOCUMENT_STORE: Dict[str, List[Dict[str, Any]]] = {}


def _get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generates dense vector embeddings using GoogleGenerativeAIEmbeddings if GOOGLE_API_KEY
    is available; falls back to a deterministic 384-dim normalized hash embedding via NumPy
    so vector search works 100% reliably offline or without embedding quota.
    """
    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        for model_name in ("models/text-embedding-004", "models/embedding-001"):
            try:
                from langchain_google_genai import GoogleGenerativeAIEmbeddings
                embedder = GoogleGenerativeAIEmbeddings(model=model_name, google_api_key=google_key)
                vecs = embedder.embed_documents(texts)
                if vecs and len(vecs) == len(texts):
                    return vecs
            except Exception:
                continue

    # Deterministic 384-dim normalized dense embedding fallback (feature hashing)
    dim = 384
    vectors: List[List[float]] = []
    for text in texts:
        vec = np.zeros(dim, dtype=np.float32)
        tokens = re.findall(r"\b[a-zA-Z0-9_]{2,}\b", text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % dim
            sign = 1.0 if ((h >> 8) & 1) else -1.0
            vec[idx] += sign
        norm = float(np.linalg.norm(vec))
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0
        vectors.append(vec.tolist())
    return vectors


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
    Recommended Next Degree, Technical Skills, and Experience.
    """
    hints: Dict[str, Any] = {}

    # 1. GPA detection
    gpa_match = re.search(
        r"(?:cgpa|gpa|grade\s*point\s*average)[^0-9\n\r]*?([0-3]\.\d{1,2}|4\.00?|\b[7-9]\.\d{1,2}\s*/\s*10)",
        text,
        re.IGNORECASE
    )
    if gpa_match:
        hints["detected_gpa"] = gpa_match.group(1).replace(" ", "")

    # 2. IELTS / TOEFL detection
    ielts_match = re.search(r"(?:ielts|band\s*score|overall\s*band)[^0-9\n\r]*?([5-9](?:\.[05])?)", text, re.IGNORECASE)
    if ielts_match:
        hints["detected_ielts"] = float(ielts_match.group(1))

    toefl_match = re.search(r"toefl[^0-9\n\r]*?(\d{2,3})", text, re.IGNORECASE)
    if toefl_match:
        hints["detected_toefl"] = int(toefl_match.group(1))

    # 3. Major / Field of Study detection
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

    # 4. Recommended Next Degree based on completed education in CV
    low = text.lower()
    if any(k in low for k in ("m.sc", "msc", "master of science", "master's degree", "m.tech", "mba")):
        hints["recommended_degree"] = "PhD"
    elif any(k in low for k in ("b.sc", "bsc", "bachelor", "b.tech", "b.e.", "undergraduate")):
        hints["recommended_degree"] = "MSc"
    elif any(k in low for k in ("high school", "a-levels", "ib diploma", "hsc", "12th grade")):
        hints["recommended_degree"] = "BSc"

    # 5. Key Skills extraction
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


def index_user_document(session_id: str, file_path: str, doc_name: str) -> Dict[str, Any]:
    """
    Extracts text, chunks it, generates vector embeddings, and persists into ChromaDB
    alongside in-memory session indexing.
    """
    pages = extract_text_from_file(file_path)
    chunks = chunk_document(pages, doc_name)

    if session_id not in SESSION_DOCUMENT_STORE:
        SESSION_DOCUMENT_STORE[session_id] = []
    SESSION_DOCUMENT_STORE[session_id].extend(chunks)

    # Persist into ChromaDB Vector Store with embeddings
    if chunks:
        texts = [c["text"] for c in chunks]
        embeddings = _get_embeddings(texts)
        ids = [f"{session_id}_{c['chunk_id']}" for c in chunks]
        metadatas = [
            {
                "session_id": session_id,
                "doc_name": c["doc_name"],
                "page": int(c["page"])
            }
            for c in chunks
        ]
        try:
            _COLLECTION.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )
        except Exception:
            pass

    full_text = "\n".join([p["text"] for p in pages])
    profile_hints = extract_profile_from_text(full_text)

    return {
        "success": True,
        "doc_name": doc_name,
        "total_pages": len(pages),
        "total_chunks": len(chunks),
        "vector_store": "ChromaDB (Persistent)",
        "profile_hints": profile_hints
    }


def retrieve_relevant_chunks(session_id: str, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
    """
    Hybrid retrieval: queries ChromaDB persistent vector store first using embeddings,
    then falls back/augments with BM25 lexical similarity.
    """
    results: List[Dict[str, Any]] = []
    seen_texts = set()

    # 1. Vector Store Semantic Query (ChromaDB)
    try:
        q_emb = _get_embeddings([query])[0]
        chroma_res = _COLLECTION.query(
            query_embeddings=[q_emb],
            where={"session_id": session_id},
            n_results=top_k
        )
        docs = (chroma_res.get("documents") or [[]])[0]
        metas = (chroma_res.get("metadatas") or [[]])[0]
        for idx, doc_txt in enumerate(docs):
            if doc_txt and doc_txt not in seen_texts:
                seen_texts.add(doc_txt)
                meta = metas[idx] if idx < len(metas) else {}
                results.append({
                    "chunk_id": f"vec_{idx}",
                    "doc_name": meta.get("doc_name", "Uploaded CV"),
                    "page": meta.get("page", 1),
                    "text": doc_txt,
                    "retrieval_method": "ChromaDB Vector"
                })
    except Exception:
        pass

    # 2. BM25 Lexical Augmentation from in-memory store
    chunks = SESSION_DOCUMENT_STORE.get(session_id, [])
    if chunks:
        q_tokens = tokenize(query)
        if q_tokens:
            doc_token_lists = [tokenize(c["text"]) for c in chunks]
            avg_len = sum(len(d) for d in doc_token_lists) / (len(doc_token_lists) or 1.0)
            scored = [(compute_bm25_similarity(q_tokens, doc_token_lists[i], avg_len), c) for i, c in enumerate(chunks)]
            scored.sort(key=lambda x: x[0], reverse=True)
            for score, item in scored[:top_k]:
                if score > 0.1 and item["text"] not in seen_texts:
                    seen_texts.add(item["text"])
                    results.append({**item, "retrieval_method": "BM25 Hybrid"})

    return results[:top_k]


def get_all_session_chunks(session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches all stored chunks for a session from ChromaDB or in-memory store."""
    chunks = SESSION_DOCUMENT_STORE.get(session_id, [])
    if chunks:
        return chunks[:limit]

    try:
        res = _COLLECTION.get(where={"session_id": session_id}, limit=limit)
        docs = res.get("documents") or []
        metas = res.get("metadatas") or []
        return [
            {
                "doc_name": (metas[i] if i < len(metas) else {}).get("doc_name", "Uploaded CV"),
                "page": (metas[i] if i < len(metas) else {}).get("page", 1),
                "text": txt
            }
            for i, txt in enumerate(docs)
        ]
    except Exception:
        return []


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
    """Returns list of unique document names uploaded in this session (ChromaDB + Memory)."""
    seen = set()
    result = []
    for c in SESSION_DOCUMENT_STORE.get(session_id, []):
        d = c["doc_name"]
        if d not in seen:
            seen.add(d)
            result.append(d)

    if not result:
        try:
            res = _COLLECTION.get(where={"session_id": session_id})
            for m in (res.get("metadatas") or []):
                d = m.get("doc_name")
                if d and d not in seen:
                    seen.add(d)
                    result.append(d)
        except Exception:
            pass

    return result
