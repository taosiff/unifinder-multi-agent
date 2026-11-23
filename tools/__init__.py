"""
tools/__init__.py - Expose all specialized tools for the UniFinder Multi-Agent system.
"""

from tools.mastersportal_tool import scrape_studyportals
from tools.web_intelligence import search_web_knowledge, fetch_webpage_content
from tools.pr_visa_tool import evaluate_immigration_pathway
from tools.career_roi_tool import calculate_roi_and_career_outlook
from tools.sop_reviewer_tool import review_statement_of_purpose
from database import search_universities, add_to_shortlist, get_shortlist, remove_from_shortlist
from tools.rag_engine import (
    index_user_document,
    retrieve_relevant_chunks,
    grade_document_relevance,
    get_session_documents
)
from tools.opportunities_tool import (
    get_live_opportunities,
    get_immigration_news,
    search_live_scholarship_opportunities
)
from tools.living_cost_tool import (
    convert_currency,
    get_city_living_cost,
    get_embassy_visa_checklist
)

__all__ = [
    "scrape_studyportals",
    "search_web_knowledge",
    "fetch_webpage_content",
    "evaluate_immigration_pathway",
    "calculate_roi_and_career_outlook",
    "review_statement_of_purpose",
    "search_universities",
    "add_to_shortlist",
    "get_shortlist",
    "remove_from_shortlist",
    "index_user_document",
    "retrieve_relevant_chunks",
    "grade_document_relevance",
    "get_session_documents",
    "get_live_opportunities",
    "get_immigration_news",
    "search_live_scholarship_opportunities",
    "convert_currency",
    "get_city_living_cost",
    "get_embassy_visa_checklist"
]
