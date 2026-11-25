"""
backend.py - UniFinder AI Multi-Agent Brain with LangGraph Subgraphs,
Persistent SqliteSaver Memory, Corrective RAG (CRAG), HITL, and Streaming.
"""

import os
import json
import uuid
import re
import asyncio
import sqlite3
from typing import TypedDict, Annotated, List, Dict, Any, Optional, AsyncGenerator
import operator
from dotenv import load_dotenv

load_dotenv()

# LangSmith Tracing configuration (optional, active if user sets keys)
if os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "unifinder-ai")

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

# LLM Providers
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

# Internal Tools, Database & RAG
from concurrent.futures import ThreadPoolExecutor
from database import search_universities, save_chat_message
from tools.mastersportal_tool import scrape_studyportals
from tools.univs_tool import search_univs_programs
from tools.university_scraper_tool import scrape_official_university_admissions
from tools.reviews_tool import fetch_university_reviews
from tools.country_job_intel_tool import (
    fetch_country_student_intelligence,
    fetch_subject_job_market_intel
)
from tools.web_intelligence import search_web_knowledge
from tools.pr_visa_tool import evaluate_immigration_pathway
from tools.career_roi_tool import calculate_roi_and_career_outlook
from tools.rag_engine import (
    retrieve_relevant_chunks,
    grade_document_relevance,
    get_all_session_chunks,
    extract_profile_from_text
)
from tools.opportunities_tool import (
    get_live_opportunities,
    get_immigration_news,
    search_live_scholarship_opportunities
)
from tools.living_cost_tool import get_city_living_cost, get_embassy_visa_checklist
from guardrails import (
    check_intent_guardrail,
    evaluate_eligibility_guardrail,
    check_budget_feasibility,
    classify_admission_chances,
    check_human_in_the_loop_trigger
)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "unifinder_memory.db")


GROQ_FALLBACK_MODELS = [
    "qwen/qwen3.8-27b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b"
]

GEMINI_FALLBACK_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-1.5-flash"
]


def get_llm(api_key_override: Optional[str] = None, provider_override: Optional[str] = None):
    """
    Dynamically loads the appropriate free online LLM (Groq or Google Gemini)
    with model-fallback resilience.
    """
    google_key = api_key_override if (provider_override == "gemini" and api_key_override) else os.getenv("GOOGLE_API_KEY")
    groq_key = api_key_override if (provider_override == "groq" and api_key_override) else os.getenv("GROQ_API_KEY")

    # Priority 1: User explicitly selected Groq or has Groq key
    if (provider_override == "groq" or not provider_override) and groq_key:
        for model_name in GROQ_FALLBACK_MODELS:
            try:
                llm = ChatGroq(model=model_name, api_key=groq_key, temperature=0.3)
                return llm
            except Exception:
                continue

    # Priority 2: Gemini
    if google_key:
        for model_name in GEMINI_FALLBACK_MODELS:
            try:
                llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=google_key, temperature=0.3)
                return llm
            except Exception:
                continue

    # Fallback to Groq if Google was preferred but failed
    if groq_key:
        for model_name in GROQ_FALLBACK_MODELS:
            try:
                return ChatGroq(model=model_name, api_key=groq_key, temperature=0.3)
            except Exception:
                continue

    return None


def _call_openai_compatible(base_url: str, api_key: str, model: str, messages: List[AnyMessage], extra_headers: Optional[Dict[str, str]] = None) -> Optional[str]:
    """Lightweight OpenAI-compatible chat completions call for Cerebras, OpenRouter, Mistral, SambaNova."""
    import requests
    formatted = []
    for m in messages:
        role = "system" if isinstance(m, SystemMessage) else ("user" if isinstance(m, HumanMessage) else "assistant")
        formatted.append({"role": role, "content": m.content})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        **(extra_headers or {})
    }
    resp = requests.post(
        base_url,
        headers=headers,
        json={"model": model, "messages": formatted, "temperature": 0.3, "max_tokens": 2500},
        timeout=25
    )
    if resp.status_code == 200:
        data = resp.json()
        choices = data.get("choices") or []
        if choices:
            return choices[0].get("message", {}).get("content", "")
    raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:150]}")


def invoke_llm_with_fallback(messages: List[AnyMessage]) -> Optional[str]:
    """
    Tries all configured FREE LLM providers in sequence during actual inference.
    If one provider hits a rate limit (429) or fails, automatically falls back to the next:
      1. Groq (GROQ_API_KEY)
      2. Google Gemini (GOOGLE_API_KEY)
      3. Cerebras (CEREBRAS_API_KEY)
      4. OpenRouter (OPENROUTER_API_KEY)
      5. Mistral AI (MISTRAL_API_KEY)
      6. SambaNova (SAMBANOVA_API_KEY)
    """
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        for model_name in GROQ_FALLBACK_MODELS:
            try:
                llm = ChatGroq(model=model_name, api_key=groq_key, temperature=0.3)
                resp = llm.invoke(messages)
                if resp and resp.content:
                    return resp.content
            except Exception:
                continue

    google_key = os.getenv("GOOGLE_API_KEY")
    if google_key:
        for model_name in GEMINI_FALLBACK_MODELS:
            try:
                llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=google_key, temperature=0.3)
                resp = llm.invoke(messages)
                if resp and resp.content:
                    return resp.content
            except Exception:
                continue

    openai_compat_providers = [
        (
            "CEREBRAS_API_KEY",
            "https://api.cerebras.ai/v1/chat/completions",
            ["llama-3.3-70b", "llama3.1-8b"],
            None
        ),
        (
            "OPENROUTER_API_KEY",
            "https://openrouter.ai/api/v1/chat/completions",
            ["meta-llama/llama-3.3-70b-instruct:free", "google/gemma-3-27b-it:free", "deepseek/deepseek-r1:free"],
            {"HTTP-Referer": "https://unifinder.local", "X-Title": "UniFinder AI"}
        ),
        (
            "MISTRAL_API_KEY",
            "https://api.mistral.ai/v1/chat/completions",
            ["mistral-small-latest", "open-mistral-nemo"],
            None
        ),
        (
            "SAMBANOVA_API_KEY",
            "https://api.sambanova.ai/v1/chat/completions",
            ["Meta-Llama-3.3-70B-Instruct", "Meta-Llama-3.1-8B-Instruct"],
            None
        ),
    ]

    for env_var, url, models, hdrs in openai_compat_providers:
        key = os.getenv(env_var)
        if not key:
            continue
        for model_name in models:
            try:
                out = _call_openai_compatible(url, key, model_name, messages, extra_headers=hdrs)
                if out:
                    return out
            except Exception:
                continue

    return None


# ==========================================
# Comprehensive State Definition
# ==========================================

class UniFinderState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    thread_id: str
    session_id: str
    degree_level: str
    subject: str
    country_pref: str
    user_gpa: float
    user_ielts: float
    budget_usd: int
    is_valid_query: bool
    guardrail_warnings: List[str]
    # RAG / Document Upload state
    uploaded_chunks: List[Dict[str, Any]]
    crag_status: str
    crag_grounding: str
    cv_extracted_profile: Dict[str, Any]
    # Discovery Subgraph outputs
    discovered_universities: List[Dict[str, Any]]
    portal_scraping_result: Dict[str, Any]
    univs_catalogue_results: List[Dict[str, Any]]
    web_search_results: str
    official_admissions_scraped: List[Dict[str, Any]]
    university_reviews: List[Dict[str, Any]]
    country_intel: Dict[str, Any]
    subject_job_market: Dict[str, Any]
    # Assessment & Opportunity outputs
    eligibility_analysis: Dict[str, Any]
    financial_analysis: Dict[str, Any]
    immigration_analysis: Dict[str, Any]
    career_roi_analysis: Dict[str, Any]
    active_opportunities: List[Dict[str, Any]]
    living_cost_details: Dict[str, Any]
    # HITL (Human-in-the-Loop) State
    hitl_required: bool
    hitl_reason: str
    hitl_options: List[str]
    hitl_approved: bool
    # Final Output
    dossier_markdown: str
    llm_calls: int


# ==========================================
# Subgraph 1: Intent & Safety Guardrail
# ==========================================

def intent_safety_node(state: UniFinderState):
    query = state["user_query"]
    guard = check_intent_guardrail(query)

    degree = state.get("degree_level") or "MSc"
    subject = state.get("subject") or ""
    country = state.get("country_pref") or ""

    q_low = query.lower()
    if "bachelor" in q_low or "bsc" in q_low or "undergrad" in q_low:
        degree = "BSc"
    elif "phd" in q_low or "doctorate" in q_low or "doctoral" in q_low:
        degree = "PhD"
    elif "master" in q_low or "msc" in q_low or "postgrad" in q_low:
        degree = "MSc"

    countries = ["germany", "united states", "usa", "uk", "united kingdom", "canada", "australia", "netherlands", "sweden", "switzerland", "singapore", "france"]
    for c in countries:
        if c in q_low and not country:
            country = "United States" if c == "usa" else "United Kingdom" if c == "uk" else c.title()
            break

    if not subject:
        for s in ["computer science", "artificial intelligence", "data science", "mechanical engineering", "biotechnology", "business", "finance", "robotics", "medicine"]:
            if s in q_low:
                subject = s.title()
                break
    if not subject:
        subject = "Computer Science"

    return {
        "is_valid_query": guard["is_relevant"],
        "degree_level": degree,
        "subject": subject,
        "country_pref": country,
        "guardrail_warnings": [guard["message"]] if not guard["is_relevant"] else []
    }


# ==========================================
# Subgraph 2: Corrective RAG (C-RAG) on Uploaded Docs
# ==========================================

def crag_retrieval_node(state: UniFinderState):
    session_id = state.get("session_id", "default_session")
    query = state["user_query"]

    # 1. Retrieve relevant chunks from user-uploaded transcripts or CV
    chunks = retrieve_relevant_chunks(session_id, query, top_k=3)
    # 2. Grade relevance
    grading = grade_document_relevance(chunks, query)

    grounding_text = ""
    if grading["status"] == "RELEVANT":
        grounding_text = "\n\n".join([f"**[Source: {c['doc_name']}, Page {c['page']}]**: {c['text']}" for c in chunks])
    elif grading["status"] == "PARTIAL_FALLBACK" and chunks:
        grounding_text = f"**[Partial Document Evidence from {chunks[0]['doc_name']}]**: {chunks[0]['text'][:350]}..."

    return {
        "uploaded_chunks": chunks,
        "crag_status": grading["status"],
        "crag_grounding": grounding_text,
        "messages": [AIMessage(content=f"C-RAG Evaluator: Retrieved {len(chunks)} document chunks. Status: {grading['status']}")]
    }


# ==========================================
# Subgraph 2B: CV Profile Extractor Node (Drives University & Program Search)
# ==========================================

def cv_profile_extractor_node(state: UniFinderState):
    """
    Reads the student's uploaded CV/Transcript from the ChromaDB vector store,
    extracts GPA, IELTS/TOEFL, Major, Skills, and Recommended Next Degree,
    and updates the search parameters so discovery_subgraph searches universities
    and programs tailored directly to the CV.
    """
    session_id = state.get("session_id", "default_session")
    all_chunks = get_all_session_chunks(session_id, limit=10)

    if not all_chunks:
        return {
            "cv_extracted_profile": {},
            "messages": [AIMessage(content="CV Extractor: No CV uploaded; using form profile parameters.")]
        }

    combined_cv = "\n".join(c.get("text", "") for c in all_chunks)
    extracted = extract_profile_from_text(combined_cv)

    updates: Dict[str, Any] = {
        "cv_extracted_profile": extracted,
        "messages": [AIMessage(content=f"CV Extractor (ChromaDB): Extracted profile {extracted} to drive university & program search.")]
    }

    # Enrich search parameters from CV if detected
    if extracted.get("detected_major"):
        updates["subject"] = extracted["detected_major"]
    if extracted.get("recommended_degree"):
        updates["degree_level"] = extracted["recommended_degree"]
    if extracted.get("detected_gpa"):
        try:
            gpa_val = float(str(extracted["detected_gpa"]).split("/")[0])
            if gpa_val <= 4.0:
                updates["user_gpa"] = gpa_val
        except ValueError:
            pass
    if extracted.get("detected_ielts"):
        updates["user_ielts"] = float(extracted["detected_ielts"])

    return updates


# ==========================================
# Stage 1: 4 Parallel Search Agent Nodes (Sharing Same State)
# ==========================================

def agent_univs_search_node(state: UniFinderState):
    res = search_univs_programs(
        query=state["subject"],
        country=state["country_pref"],
        degree_level=state["degree_level"],
        limit=8
    )
    programs = res.get("programs", []) if isinstance(res, dict) else []
    return {
        "univs_catalogue_results": programs,
        "messages": [AIMessage(content=f"Univs.com Agent: Found {len(programs)} live programs.")]
    }


def agent_studyportals_scraper_node(state: UniFinderState):
    portal_data = scrape_studyportals(
        degree_level=state["degree_level"],
        subject=state["subject"],
        country=state["country_pref"]
    )
    return {
        "portal_scraping_result": portal_data,
        "messages": [AIMessage(content="StudyPortals Agent: Scraped portal listings.")]
    }


def agent_web_search_node(state: UniFinderState):
    web_query = f"top universities {state['degree_level']} {state['subject']} {state['country_pref']} tuition admission".strip()
    web_data = search_web_knowledge(web_query, 4)
    return {
        "web_search_results": json.dumps(web_data, default=str),
        "messages": [AIMessage(content=f"Web Search Agent: Gathered {len(web_data)} live web results.")]
    }


def agent_db_search_node(state: UniFinderState):
    budget = state.get("budget_usd", 0)
    gpa = state.get("user_gpa", 0.0)
    country = state["country_pref"]
    db_results = search_universities(
        degree_level=state["degree_level"],
        subject=state["subject"],
        country=country,
        max_tuition=budget if budget > 5000 else None,
        user_gpa=gpa if gpa > 0 else None,
        limit=6
    )
    if not db_results and country:
        db_results = search_universities(degree_level=state["degree_level"], subject=state["subject"], country=None, limit=6)
    return {
        "discovered_universities": db_results,
        "messages": [AIMessage(content=f"Database Agent: Matched {len(db_results)} curated institutions.")]
    }


def merge_discovery_node(state: UniFinderState):
    """Synchronization barrier after the 4 parallel search agents finish."""
    return {
        "messages": [AIMessage(content="Discovery Fan-In: All 4 parallel search agents completed. Launching parallel review, admissions, and scholarship agents.")]
    }


# Keep backward-compatible helper alias for direct unit tests
def discovery_subgraph_node(state: UniFinderState):
    with ThreadPoolExecutor(max_workers=4) as executor:
        f1 = executor.submit(agent_univs_search_node, state)
        f2 = executor.submit(agent_studyportals_scraper_node, state)
        f3 = executor.submit(agent_web_search_node, state)
        f4 = executor.submit(agent_db_search_node, state)
        r1, r2, r3, r4 = f1.result(), f2.result(), f3.result(), f4.result()
    return {
        **r1, **r2, **r3, **r4,
        "messages": r1["messages"] + r2["messages"] + r3["messages"] + r4["messages"]
    }


# ==========================================
# Stage 2: Parallel Enrichment Agents (Official Admissions, Reddit Reviews, Scholarships, PR/ROI)
# ==========================================

def reddit_reviews_node(state: UniFinderState):
    """Parallel Agent: Extracts student & alumni reviews from Reddit RSS + web forums."""
    unis = state.get("discovered_universities", [])
    reviews = fetch_university_reviews(
        universities=unis,
        degree_level=state.get("degree_level", "MSc"),
        subject=state.get("subject", "Computer Science")
    )
    return {
        "university_reviews": reviews,
        "messages": [AIMessage(content=f"Reddit & Reviews Agent: Extracted student/alumni reviews for {len(reviews)} universities.")]
    }


def country_intel_node(state: UniFinderState):
    """Parallel Agent: Researches target country economics, PR rules & student-friendliness."""
    country = state.get("country_pref") or "Germany"
    intel = fetch_country_student_intelligence(country=country)
    return {
        "country_intel": intel,
        "messages": [AIMessage(content=f"Country & Economy Agent: Analyzed economics, student-friendliness & PR for {country}.")]
    }


def subject_job_market_node(state: UniFinderState):
    """Parallel Agent: Researches subject job demand & post-study sponsored visa reality."""
    country = state.get("country_pref") or "Germany"
    subject = state.get("subject") or "Computer Science"
    degree = state.get("degree_level") or "MSc"
    job_intel = fetch_subject_job_market_intel(country=country, subject=subject, degree_level=degree)
    return {
        "subject_job_market": job_intel,
        "messages": [AIMessage(content=f"Job & Sponsored Visa Agent: Analyzed {subject} job market & sponsorship in {country}.")]
    }


# ==========================================
# Subgraph 3B: Official University Website & Admissions Scraper Subgraph
# ==========================================

def official_site_admissions_node(state: UniFinderState):
    unis = state.get("discovered_universities", [])
    degree = state.get("degree_level", "MSc")
    subject = state.get("subject", "Computer Science")

    targets = unis[:2]
    scraped_list: List[Dict[str, Any]] = []

    if targets:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(
                    scrape_official_university_admissions,
                    university_name=u.get("name", ""),
                    official_url=u.get("website", ""),
                    degree_level=degree,
                    subject=subject
                )
                for u in targets
            ]
            for fut in futures:
                res = fut.result()
                if res.get("success") and res.get("data"):
                    scraped_list.append(res["data"])

    return {
        "official_admissions_scraped": scraped_list,
        "messages": [AIMessage(content=f"Official Website Scraper Subgraph: Extracted tuition, IELTS/TOEFL, GPA, and deadlines for {len(scraped_list)} institutions.")]
    }


# ==========================================
# Subgraph 4: Opportunities & Live News Subgraph
# ==========================================

def opportunities_subgraph_node(state: UniFinderState):
    country = state.get("country_pref", "")
    degree = state.get("degree_level", "MSc")

    matched_opportunities = get_live_opportunities(
        destination=country,
        degree_level=degree
    )

    return {
        "active_opportunities": matched_opportunities[:5],
        "messages": [AIMessage(content=f"Opportunities Subgraph: Matched {len(matched_opportunities)} active global scholarships.")]
    }


# ==========================================
# Subgraph 5: Admission, Living Cost & Immigration
# ==========================================

def assessment_and_visa_node(state: UniFinderState):
    gpa = state.get("user_gpa", 3.4)
    ielts = state.get("user_ielts", 6.5)
    country = state.get("country_pref") or "Germany"
    degree = state.get("degree_level", "MSc")
    subject = state.get("subject", "Computer Science")
    budget = state.get("budget_usd", 25000)

    # 1. Eligibility Check
    eligibility_report = evaluate_eligibility_guardrail(
        user_gpa=gpa, user_ielts=ielts, target_country=country, target_degree=degree
    )

    # 2. Classify admission chances
    classified = []
    for uni in state.get("discovered_universities", []):
        min_gpa = uni.get("min_gpa", 3.0)
        acceptance = uni.get("acceptance_rate_percent", 30.0)
        tier = classify_admission_chances(gpa, min_gpa, acceptance)
        classified.append({
            "name": uni["name"], "country": uni["country"], "tier": tier,
            "min_gpa": min_gpa, "acceptance_rate": f"{acceptance}%",
            "tuition_usd": uni.get("tuition_fee_annual_usd", 0)
        })

    # 3. Immigration Pathway
    imm_eval = evaluate_immigration_pathway(country=country, degree_level=degree, major=subject)

    # 4. Living Cost & Checklist
    first_city = state.get("discovered_universities", [{}])[0].get("city", "Munich") if state.get("discovered_universities") else "Munich"
    living_cost = get_city_living_cost(first_city)

    # 5. Career & ROI Forecaster
    unis = state.get("discovered_universities", [])
    avg_tuition = sum(u.get("tuition_fee_annual_usd", 15000) for u in unis) // (len(unis) or 1)
    avg_living = sum(u.get("living_cost_annual_usd", 14000) for u in unis) // (len(unis) or 1)
    roi_metrics = calculate_roi_and_career_outlook(
        country=country, subject=subject, degree_level=degree,
        annual_tuition_usd=avg_tuition, annual_living_cost_usd=avg_living,
        program_duration_years=2.0 if degree == "MSc" else 4.0 if degree == "BSc" else 3.5
    )

    # 6. HITL Trigger evaluation
    hitl_check = check_human_in_the_loop_trigger(
        user_budget_usd=budget, discovered_unis=classified, user_gpa=gpa, country=country
    )

    return {
        "eligibility_analysis": {
            "user_gpa": gpa, "user_ielts": ielts,
            "hard_hurdles": eligibility_report["hard_hurdles"],
            "advisory_notes": eligibility_report["advisory_notes"],
            "classified_universities": classified
        },
        "immigration_analysis": imm_eval,
        "living_cost_details": living_cost,
        "career_roi_analysis": roi_metrics,
        "hitl_required": hitl_check["requires_hitl"],
        "hitl_reason": hitl_check["hitl_reason"],
        "hitl_options": hitl_check["action_options"]
    }


# ==========================================
# Subgraph 6: Synthesis Counselor Node
# ==========================================

def synthesis_counselor_node(state: UniFinderState):
    llm = get_llm()
    user_query = state["user_query"]
    unis = state.get("discovered_universities", [])
    univs_live = state.get("univs_catalogue_results", [])
    official_scraped = state.get("official_admissions_scraped", [])
    uni_reviews = state.get("university_reviews", [])
    country_intel = state.get("country_intel", {})
    job_market = state.get("subject_job_market", {})
    web_search = state.get("web_search_results", "")

    # Include recent conversation turns from checkpointer memory for follow-up continuity
    prior_turns = []
    for m in (state.get("messages") or [])[-8:]:
        if isinstance(m, HumanMessage):
            prior_turns.append(f"User: {m.content[:250]}")
        elif isinstance(m, AIMessage) and len(m.content) > 120:
            prior_turns.append(f"Assistant (prev): {m.content[:300]}...")
    history_block = "\n".join(prior_turns[:-1]) if len(prior_turns) > 1 else ""
    eligibility = state.get("eligibility_analysis", {})
    immigration = state.get("immigration_analysis", {})
    career = state.get("career_roi_analysis", {})
    opps = state.get("active_opportunities", [])
    crag_grounding = state.get("crag_grounding", "")
    cv_profile = state.get("cv_extracted_profile", {})
    living = state.get("living_cost_details", {})

    prompt = f"""
You are UniFinder AI, the global authority on university admissions, scholarships, post-graduation visas, and career ROI.
Synthesize the structured analysis below into an authoritative, inspiring, and actionable Executive Higher-Education Dossier.

USER REQUEST:
"{user_query}"

{f"CONVERSATION HISTORY (FOLLOW-UP CONTEXT):\n{history_block}\n" if history_block else ""}

STUDENT PROFILE CONSTRAINTS:
- Degree Level: {state.get('degree_level')}
- Major: {state.get('subject')}
- Country Preference: {state.get('country_pref') or 'Global Top Options'}
- Academic GPA: {eligibility.get('user_gpa', 3.4)}/4.0 | IELTS: {eligibility.get('user_ielts', 6.5)}
- Annual Budget: ${state.get('budget_usd', 25000):,} USD

{f"CV EXTRACTED PROFILE (FROM CHROMADB VECTOR STORE):\n{json.dumps(cv_profile, indent=2)}\n" if cv_profile else ""}
{f"DOCUMENT EVIDENCE (FROM UPLOADED STUDENT TRANSCRIPT/CV VIA CORRECTIVE RAG):\n{crag_grounding}\n" if crag_grounding else ""}

DISCOVERED UNIVERSITIES (CURATED DATABASE):
{json.dumps(unis[:4], indent=2, default=str)}

LIVE UNIVS.COM CATALOGUE MATCHES (22,900+ INSTITUTES):
{json.dumps(univs_live[:5], indent=2, default=str)}

OFFICIAL UNIVERSITY WEBSITE SCRAPED ADMISSIONS (TUITION, IELTS/TOEFL, GPA, DEADLINES, INTAKES & PROGRAMS):
{json.dumps(official_scraped, indent=2, default=str)}

STUDENT & ALUMNI REVIEWS (REDDIT & FORUMS):
{json.dumps(uni_reviews, indent=2, default=str)}

COUNTRY ECONOMICS, STUDENT-FRIENDLINESS & PR OVERVIEW:
{json.dumps(country_intel, indent=2, default=str)}

SUBJECT JOB CONDITIONS & AFTER-STUDY SPONSORED VISA REALITY:
{json.dumps(job_market, indent=2, default=str)}

LIVE WEB INTELLIGENCE (DUCKDUCKGO / GOOGLE PARALLEL SEARCH):
{web_search[:1200] if web_search else "N/A"}

ADMISSION CHANCE TIERS:
{json.dumps(eligibility.get('classified_universities', []), indent=2, default=str)}

ACTIVE SCHOLARSHIPS & FUNDING OPPORTUNITIES:
{json.dumps(opps[:3], indent=2, default=str)}

IMMIGRATION, WORK PERMIT & PR ROADMAP:
- Destination: {immigration.get('country')}
- Post-Study Work Permit (PSWV): {immigration.get('pswv_duration')}
- PR Pathway: {immigration.get('pr_pathway')} (Timeline: {immigration.get('pr_timeline')})
- Salary Minimum: {immigration.get('salary_threshold')}
- Living Expenses & Visa Proof: {immigration.get('financial_proof')}

CITY LIVING COSTS:
{json.dumps(living, indent=2, default=str)}

CAREER & ROI FORECAST:
- Starting Salary: ${career.get('projected_starting_salary_avg_usd', 75000):,} USD/year
- Payback Period: {career.get('payback_period_years', 2.0)} Years ({career.get('roi_rating')} ROI)
- 3-Year Cumulative Net Profit: ${career.get('three_year_net_profit_usd', 25000):,} USD

FORMAT THE RESPONSE BEAUTIFULLY WITH:
# 🎓 Executive Admissions & Career Dossier
## 1. Profile Assessment & Strategy Overview {f'(incorporating your uploaded document)' if crag_grounding else ''}
## 2. Recommended Universities & Program Matches (Include Reach, Target, Safety classifications)
## 3. Active Scholarship Opportunities & Funding Strategy
## 4. Post-Study Work Visa (PSWV) & Permanent Residency (PR) Roadmap
## 5. Job Market Outlook, Top Employers & ROI Forecast
## 6. Actionable Next Steps & Timeline
"""

    msgs = [
        SystemMessage(content="You are an expert AI Education and Global Immigration Counselor. Use clean markdown formatting."),
        HumanMessage(content=prompt)
    ]
    llm_output = invoke_llm_with_fallback(msgs)
    if llm_output:
        dossier = llm_output
        calls = state.get("llm_calls", 0) + 1
    else:
        dossier = generate_rule_based_dossier(state)
        calls = state.get("llm_calls", 0)

    return {
        "dossier_markdown": dossier,
        "llm_calls": calls,
        "messages": [AIMessage(content=dossier)]
    }


def generate_rule_based_dossier(state: UniFinderState, error_msg: str = "") -> str:
    degree = state.get("degree_level", "MSc")
    subject = state.get("subject", "Computer Science")
    country = state.get("country_pref") or "Global Destinations"
    unis = state.get("discovered_universities", [])
    univs_live = state.get("univs_catalogue_results", [])
    official_scraped = state.get("official_admissions_scraped", [])
    uni_reviews = state.get("university_reviews", [])
    country_intel = state.get("country_intel", {})
    job_market = state.get("subject_job_market", {})
    web_search = state.get("web_search_results", "")

    # Include recent conversation turns from checkpointer memory for follow-up continuity
    prior_turns = []
    for m in (state.get("messages") or [])[-8:]:
        if isinstance(m, HumanMessage):
            prior_turns.append(f"User: {m.content[:250]}")
        elif isinstance(m, AIMessage) and len(m.content) > 120:
            prior_turns.append(f"Assistant (prev): {m.content[:300]}...")
    history_block = "\n".join(prior_turns[:-1]) if len(prior_turns) > 1 else ""
    eligibility = state.get("eligibility_analysis", {})
    immigration = state.get("immigration_analysis", {})
    career = state.get("career_roi_analysis", {})
    opps = state.get("active_opportunities", [])
    crag_grounding = state.get("crag_grounding", "")

    api_notice = ""
    if error_msg:
        api_notice = f"> ⚠️ **LLM Connection Note**: {error_msg}. Generated using verified local database and intelligence tools.\n\n"
    elif not os.getenv("GOOGLE_API_KEY") and not os.getenv("GROQ_API_KEY"):
        api_notice = "> 💡 **Tip**: Add your free Google Gemini or Groq API key in the API Settings modal or `.env` file to enable dynamic AI reasoning.\n\n"

    uni_rows = ""
    for u in unis:
        uni_rows += f"- **{u['name']}** ({u['country']}, {u['city']}) | QS Rank: #{u.get('world_ranking', 'N/A')} | Annual Tuition: ${u.get('tuition_fee_annual_usd', 0):,} | Min GPA: {u.get('min_gpa', 3.0)} | [Official Website]({u.get('official_url', '#')})\n"

    opp_rows = ""
    for o in opps[:3]:
        opp_rows += f"- 🌟 **{o['title']}** ({o['destination']}) — **{o['funding_type']}** | Deadline: {o['deadline']} | [Learn More]({o['official_url']})\n"

    crag_section = ""
    if crag_grounding:
        crag_section = f"### 📄 Uploaded Document Insights (C-RAG):\n{crag_grounding}\n\n---\n"

    return f"""{api_notice}# 🎓 Executive Admissions & Career Dossier: {degree} in {subject}

## 1. Profile Assessment & Strategy Overview
- **Degree Level**: {degree}
- **Discipline**: {subject}
- **Target Country**: {country}
- **Academic Profile**: GPA {eligibility.get('user_gpa', 3.4)}/4.0 | IELTS {eligibility.get('user_ielts', 6.5)}
- **Annual Investment Budget**: ${state.get('budget_usd', 25000):,} USD

{crag_section}### Eligibility Check & Critical Guardrails:
{"".join([f"- ⚠️ {h}\n" for h in eligibility.get("hard_hurdles", [])]) or "- ✅ No hard disqualifying hurdles detected."}
{"".join([f"- ℹ️ {a}\n" for a in eligibility.get("advisory_notes", [])])}

---

## 2. Recommended Universities & Program Matches
{uni_rows or "- Universities matching criteria are available in the University Matrix."}

---

## 3. Active Scholarship Opportunities & Funding
{opp_rows or "- Explore DAAD (Germany), Erasmus Mundus (EU), Fulbright (USA), and Chevening (UK) for comprehensive funding."}
- **Proof of Living Funds / Visa Requirement**: {immigration.get('financial_proof', 'Standard proof of living funds (~$12,000 - $20,000 USD/year) required for student visa.')}

---

## 4. Post-Study Work Visa (PSWV) & Permanent Residency (PR) Roadmap
- **Country**: {immigration.get('country', country)}
- **Post-Graduation Work Permit**: {immigration.get('pswv_duration', '1 to 3 Years')}
- **PR Pathway**: {immigration.get('pr_pathway', 'Points-tested skilled migration or employer sponsorship')}
- **PR Timeline**: {immigration.get('pr_timeline', '2 to 5 years of post-study employment')}
- **Minimum Qualifying Salary**: {immigration.get('salary_threshold', 'Prevailing median wage')}
- **PR Feasibility Index**: **{immigration.get('pr_difficulty', 'Moderate')}**

---

## 5. Job Market Outlook & Financial ROI
- **Industry Demand**: **{career.get('industry_demand', 'High')}**
- **Projected Starting Salary**: **${career.get('projected_starting_salary_avg_usd', 75000):,} USD / year**
- **Net Program Investment**: ${career.get('net_total_investment_usd', 45000):,} USD
- **Payback Period**: **{career.get('payback_period_years', 2.0)} Years** ({career.get('roi_rating')} ROI)
- **3-Year Cumulative Net Profit**: **${career.get('three_year_net_profit_usd', 25000):,} USD**

---

## 6. Actionable Next Steps & Timeline
1. **Testing**: Schedule IELTS/TOEFL and GRE (if targeting top North American research programs).
2. **Documents**: Draft Statement of Purpose and request letters of recommendation.
3. **Application Rounds**: Submit by December 15 - January 15 for priority consideration.
4. **Visa Preparation**: Open Blocked Account (Germany) or secure GIC (Canada) promptly upon receiving your unconditional admission offer.
"""


# ==========================================
# Build LangGraph Network with Subgraphs & SqliteSaver
# ==========================================

def get_checkpointer():
    """
    Dual-mode checkpointer:
    Uses PostgreSQL (PostgresSaver) in production (Render, Neon, Supabase)
    or SQLite (SqliteSaver) when running locally.
    """
    database_url = os.getenv("DATABASE_URL")
    if database_url and database_url.startswith("postgres"):
        from langgraph.checkpoint.postgres import PostgresSaver
        import psycopg
        from psycopg.rows import dict_row

        if "sslmode=" not in database_url:
            separator = "&" if "?" in database_url else "?"
            database_url = f"{database_url}{separator}sslmode=require"

        conn = psycopg.connect(database_url, autocommit=True, row_factory=dict_row)
        saver = PostgresSaver(conn)
        saver.setup()
        return saver
    else:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        saver = SqliteSaver(conn)
        saver.setup()
        return saver


def create_unifinder_graph():
    graph = StateGraph(UniFinderState)

    # Entry & CV Memory Nodes
    graph.add_node("intent_safety", intent_safety_node)
    graph.add_node("crag_retrieval", crag_retrieval_node)
    graph.add_node("cv_profile_extractor", cv_profile_extractor_node)

    # Stage 1: 4 Parallel Search Agent Nodes
    graph.add_node("agent_univs_search", agent_univs_search_node)
    graph.add_node("agent_studyportals_scraper", agent_studyportals_scraper_node)
    graph.add_node("agent_web_search", agent_web_search_node)
    graph.add_node("agent_db_search", agent_db_search_node)
    graph.add_node("merge_discovery", merge_discovery_node)

    # Stage 2: 6 Parallel Enrichment Agent Nodes
    graph.add_node("agent_official_admissions", official_site_admissions_node)
    graph.add_node("agent_reddit_reviews", reddit_reviews_node)
    graph.add_node("agent_scholarship_finder", opportunities_subgraph_node)
    graph.add_node("agent_assessment_visa", assessment_and_visa_node)
    graph.add_node("agent_country_intel", country_intel_node)
    graph.add_node("agent_subject_job_market", subject_job_market_node)

    # Stage 3: Final Answer Generator Agent Node
    graph.add_node("answer_generator", synthesis_counselor_node)

    # Wiring: Sequential Entry -> 4-Way Parallel Search -> Fan-In -> 6-Way Parallel Enrichment -> Answer Generator
    graph.add_edge(START, "intent_safety")
    graph.add_edge("intent_safety", "crag_retrieval")
    graph.add_edge("crag_retrieval", "cv_profile_extractor")

    search_agents = [
        "agent_univs_search",
        "agent_studyportals_scraper",
        "agent_web_search",
        "agent_db_search",
    ]
    for sa in search_agents:
        graph.add_edge("cv_profile_extractor", sa)
        graph.add_edge(sa, "merge_discovery")

    enrichment_agents = [
        "agent_official_admissions",
        "agent_reddit_reviews",
        "agent_scholarship_finder",
        "agent_assessment_visa",
        "agent_country_intel",
        "agent_subject_job_market",
    ]
    for ea in enrichment_agents:
        graph.add_edge("merge_discovery", ea)
        graph.add_edge(ea, "answer_generator")

    graph.add_edge("answer_generator", END)

    checkpointer = get_checkpointer()
    return graph.compile(checkpointer=checkpointer)


unifinder_graph = create_unifinder_graph()


def run_unifinder_agent(
    user_input: str,
    thread_id: Optional[str] = None,
    session_id: Optional[str] = None,
    degree_level: str = "MSc",
    subject: str = "Computer Science",
    country: str = "",
    user_gpa: float = 3.4,
    user_ielts: float = 6.5,
    budget_usd: int = 25000,
    api_key_override: Optional[str] = None,
    provider_override: Optional[str] = None
) -> Dict[str, Any]:
    if not thread_id:
        thread_id = f"student_{uuid.uuid4().hex[:8]}"
    if not session_id:
        session_id = thread_id

    config = {"configurable": {"thread_id": thread_id}}

    if api_key_override:
        if provider_override == "gemini":
            os.environ["GOOGLE_API_KEY"] = api_key_override
        elif provider_override == "groq":
            os.environ["GROQ_API_KEY"] = api_key_override

    initial_state: UniFinderState = {
        "messages": [HumanMessage(content=user_input)],
        "user_query": user_input,
        "thread_id": thread_id,
        "session_id": session_id,
        "degree_level": degree_level,
        "subject": subject,
        "country_pref": country,
        "user_gpa": user_gpa,
        "user_ielts": user_ielts,
        "budget_usd": budget_usd,
        "is_valid_query": True,
        "guardrail_warnings": [],
        "uploaded_chunks": [],
        "crag_status": "",
        "crag_grounding": "",
        "cv_extracted_profile": {},
        "discovered_universities": [],
        "portal_scraping_result": {},
        "univs_catalogue_results": [],
        "web_search_results": "",
        "official_admissions_scraped": [],
        "university_reviews": [],
        "country_intel": {},
        "subject_job_market": {},
        "eligibility_analysis": {},
        "financial_analysis": {},
        "immigration_analysis": {},
        "career_roi_analysis": {},
        "active_opportunities": [],
        "living_cost_details": {},
        "hitl_required": False,
        "hitl_reason": "",
        "hitl_options": [],
        "hitl_approved": False,
        "dossier_markdown": "",
        "llm_calls": 0
    }

    result = unifinder_graph.invoke(initial_state, config=config)
    dossier = result.get("dossier_markdown", "")
    save_chat_message(thread_id, "user", user_input)
    if dossier:
        save_chat_message(thread_id, "assistant", dossier)

    return {
        "thread_id": thread_id,
        "session_id": session_id,
        "dossier": result.get("dossier_markdown", ""),
        "discovered_universities": result.get("discovered_universities", []),
        "portal_scraping_result": result.get("portal_scraping_result", {}),
        "univs_catalogue_results": result.get("univs_catalogue_results", []),
        "web_search_results": result.get("web_search_results", ""),
        "official_admissions_scraped": result.get("official_admissions_scraped", []),
        "university_reviews": result.get("university_reviews", []),
        "country_intel": result.get("country_intel", {}),
        "subject_job_market": result.get("subject_job_market", {}),
        "eligibility_analysis": result.get("eligibility_analysis", {}),
        "immigration_analysis": result.get("immigration_analysis", {}),
        "career_roi_analysis": result.get("career_roi_analysis", {}),
        "active_opportunities": result.get("active_opportunities", []),
        "living_cost_details": result.get("living_cost_details", {}),
        "crag_status": result.get("crag_status", ""),
        "crag_grounding": result.get("crag_grounding", ""),
        "cv_extracted_profile": result.get("cv_extracted_profile", {}),
        "hitl_required": result.get("hitl_required", False),
        "hitl_reason": result.get("hitl_reason", ""),
        "hitl_options": result.get("hitl_options", []),
        "degree_level": result.get("degree_level", degree_level),
        "subject": result.get("subject", subject),
        "country_pref": result.get("country_pref", country),
        "llm_calls": result.get("llm_calls", 0)
    }


async def run_unifinder_agent_stream(
    user_input: str,
    thread_id: str,
    session_id: str,
    degree_level: str = "MSc",
    subject: str = "Computer Science",
    country: str = "",
    user_gpa: float = 3.4,
    user_ielts: float = 6.5,
    budget_usd: int = 25000,
    api_key_override: Optional[str] = None,
    provider_override: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """
    Real-time LangGraph streaming generator emitting live parallel agent completion events
    and token-by-token Answer Generator streaming via Server-Sent Events (SSE).
    """
    if not thread_id:
        thread_id = f"student_{uuid.uuid4().hex[:8]}"
    if not session_id:
        session_id = thread_id

    config = {"configurable": {"thread_id": thread_id}}

    if api_key_override:
        if provider_override == "gemini":
            os.environ["GOOGLE_API_KEY"] = api_key_override
        elif provider_override == "groq":
            os.environ["GROQ_API_KEY"] = api_key_override

    initial_state: UniFinderState = {
        "messages": [HumanMessage(content=user_input)],
        "user_query": user_input,
        "thread_id": thread_id,
        "session_id": session_id,
        "degree_level": degree_level,
        "subject": subject,
        "country_pref": country,
        "user_gpa": user_gpa,
        "user_ielts": user_ielts,
        "budget_usd": budget_usd,
        "is_valid_query": True,
        "guardrail_warnings": [],
        "uploaded_chunks": [],
        "crag_status": "",
        "crag_grounding": "",
        "cv_extracted_profile": {},
        "discovered_universities": [],
        "portal_scraping_result": {},
        "univs_catalogue_results": [],
        "web_search_results": "",
        "official_admissions_scraped": [],
        "university_reviews": [],
        "country_intel": {},
        "subject_job_market": {},
        "eligibility_analysis": {},
        "financial_analysis": {},
        "immigration_analysis": {},
        "career_roi_analysis": {},
        "active_opportunities": [],
        "living_cost_details": {},
        "hitl_required": False,
        "hitl_reason": "",
        "hitl_options": [],
        "hitl_approved": False,
        "dossier_markdown": "",
        "llm_calls": 0
    }

    # High-level, clean status phases (keeps internal tools discreet)
    phase_map = {
        "intent_safety": "Analyzing your profile & goals...",
        "crag_retrieval": "Reviewing your uploaded documents...",
        "cv_profile_extractor": "Matching profile criteria...",
        "agent_univs_search": "Exploring global universities & programs...",
        "agent_studyportals_scraper": "Exploring global universities & programs...",
        "agent_web_search": "Exploring global universities & programs...",
        "agent_db_search": "Exploring global universities & programs...",
        "merge_discovery": "Shortlisting top institutions...",
        "agent_official_admissions": "Checking admissions, costs & deadlines...",
        "agent_reddit_reviews": "Checking student experiences & reviews...",
        "agent_scholarship_finder": "Checking scholarships & funding...",
        "agent_assessment_visa": "Evaluating visas, living costs & ROI...",
        "agent_country_intel": "Evaluating country & PR pathways...",
        "agent_subject_job_market": "Evaluating career & job outlook...",
        "answer_generator": "Writing your tailored recommendation...",
    }

    save_chat_message(thread_id, "user", user_input)
    accumulated: Dict[str, Any] = dict(initial_state)
    last_phase = ""
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def _run_sync_stream():
        try:
            for update in unifinder_graph.stream(initial_state, config=config, stream_mode="updates"):
                loop.call_soon_threadsafe(queue.put_nowait, ("update", update))
        except Exception as exc:
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(exc)))
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    loop.run_in_executor(None, _run_sync_stream)

    while True:
        kind, payload = await queue.get()
        if kind == "done":
            break
        if kind == "error":
            raise RuntimeError(payload)
        for node_name, node_out in payload.items():
            if isinstance(node_out, dict):
                for k, v in node_out.items():
                    if k != "messages":
                        accumulated[k] = v

                phase_text = phase_map.get(node_name, "Researching...")
                if phase_text != last_phase:
                    last_phase = phase_text
                    yield f"data: {json.dumps({'type': 'phase', 'text': phase_text})}\n\n"

    dossier = accumulated.get("dossier_markdown", "")
    if dossier:
        save_chat_message(thread_id, "assistant", dossier)
    chunk_size = 45
    for i in range(0, len(dossier), chunk_size):
        chunk = dossier[i:i + chunk_size]
        yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
        await asyncio.sleep(0.012)

    final_res = {
        "thread_id": thread_id,
        "session_id": session_id,
        "dossier": dossier,
        "discovered_universities": accumulated.get("discovered_universities", []),
        "portal_scraping_result": accumulated.get("portal_scraping_result", {}),
        "univs_catalogue_results": accumulated.get("univs_catalogue_results", []),
        "web_search_results": accumulated.get("web_search_results", ""),
        "official_admissions_scraped": accumulated.get("official_admissions_scraped", []),
        "university_reviews": accumulated.get("university_reviews", []),
        "country_intel": accumulated.get("country_intel", {}),
        "subject_job_market": accumulated.get("subject_job_market", {}),
        "eligibility_analysis": accumulated.get("eligibility_analysis", {}),
        "immigration_analysis": accumulated.get("immigration_analysis", {}),
        "career_roi_analysis": accumulated.get("career_roi_analysis", {}),
        "active_opportunities": accumulated.get("active_opportunities", []),
        "living_cost_details": accumulated.get("living_cost_details", {}),
        "crag_status": accumulated.get("crag_status", ""),
        "crag_grounding": accumulated.get("crag_grounding", ""),
        "cv_extracted_profile": accumulated.get("cv_extracted_profile", {}),
        "hitl_required": accumulated.get("hitl_required", False),
        "hitl_reason": accumulated.get("hitl_reason", ""),
        "hitl_options": accumulated.get("hitl_options", []),
        "degree_level": accumulated.get("degree_level", degree_level),
        "subject": accumulated.get("subject", subject),
        "country_pref": accumulated.get("country_pref", country),
        "llm_calls": accumulated.get("llm_calls", 0)
    }
    yield f"data: {json.dumps({'type': 'complete', 'data': final_res}, default=str)}\n\n"
