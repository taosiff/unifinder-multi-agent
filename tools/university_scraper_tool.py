"""
tools/university_scraper_tool.py - Official University Website & Admissions Scraper + LangGraph Subgraph
Crawls a university's main website and admissions/programs subpages using BeautifulSoup4,
and extracts:
  - Tuition fees
  - IELTS / TOEFL requirements
  - GPA requirements
  - Deadlines and intakes
  - Degree programs
"""

import re
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional, TypedDict

import requests
from bs4 import BeautifulSoup
from langgraph.graph import StateGraph, START, END

from tools.web_intelligence import search_web_knowledge

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

KNOWN_OFFICIAL_DOMAINS = {
    "technical university of munich": "https://www.tum.de/en/",
    "tum": "https://www.tum.de/en/",
    "rwth aachen": "https://www.rwth-aachen.de/cms/~a/root/?lidx=1",
    "eth zurich": "https://ethz.ch/en.html",
    "university of toronto": "https://www.utoronto.ca/",
    "university of british columbia": "https://www.ubc.ca/",
    "ubc": "https://www.ubc.ca/",
    "mit": "https://www.mit.edu/",
    "massachusetts institute of technology": "https://www.mit.edu/",
    "stanford university": "https://www.stanford.edu/",
    "university of oxford": "https://www.ox.ac.uk/",
    "university of cambridge": "https://www.cam.ac.uk/",
    "imperial college london": "https://www.imperial.ac.uk/",
    "delft university of technology": "https://www.tudelft.nl/en/",
    "tu delft": "https://www.tudelft.nl/en/",
    "university of melbourne": "https://www.unimelb.edu.au/",
    "national university of singapore": "https://nus.edu.sg/",
    "nus": "https://nus.edu.sg/",
    "kth royal institute of technology": "https://www.kth.se/en",
}

ADMISSION_LINK_KEYWORDS = (
    "admission", "admissions", "apply", "tuition", "fee", "fees",
    "requirement", "requirements", "deadline", "deadlines", "intake",
    "english", "ielts", "toefl", "program", "programs", "programme",
    "study", "graduate", "undergraduate", "international"
)


def _fetch_html(url: str, timeout: int = 8) -> Optional[str]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("Content-Type", "text/html"):
            return resp.text
    except Exception:
        pass
    return None


def _clean_text(html: str, max_chars: int = 12000) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)[:max_chars]


def _discover_subpages(base_url: str, html: str, max_links: int = 4) -> List[str]:
    """Finds same-domain admissions, tuition, and programs subpages from the main page."""
    soup = BeautifulSoup(html, "html.parser")
    base_parsed = urllib.parse.urlparse(base_url)
    base_domain = base_parsed.netloc.lower().replace("www.", "")

    scored: List[tuple[int, str]] = []
    seen = {base_url.rstrip("/")}

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        full_url = urllib.parse.urljoin(base_url, href)
        parsed = urllib.parse.urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            continue
        domain = parsed.netloc.lower().replace("www.", "")
        if base_domain not in domain and domain not in base_domain:
            continue

        norm_url = full_url.split("#")[0].rstrip("/")
        if norm_url in seen:
            continue

        haystack = f"{parsed.path.lower()} {a.get_text(' ', strip=True).lower()}"
        score = sum(2 if kw in parsed.path.lower() else 1 for kw in ADMISSION_LINK_KEYWORDS if kw in haystack)
        if score > 0:
            seen.add(norm_url)
            scored.append((score, norm_url))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [u for _, u in scored[:max_links]]


def _extract_programs_from_html(html: str, subject: str = "") -> List[str]:
    """Extracts candidate degree/program titles from scraped HTML."""
    soup = BeautifulSoup(html, "html.parser")
    program_keywords = re.compile(
        r"\b(B\.?Sc|M\.?Sc|Ph\.?D|Bachelor|Master|Doctorate|Computer Science|Data Science|"
        r"Artificial Intelligence|Engineering|Business|Finance|Biotechnology|Robotics|Cybersecurity)\b",
        re.IGNORECASE
    )
    found: List[str] = []
    seen = set()

    for tag in soup.find_all(["a", "h2", "h3", "h4", "li"]):
        txt = re.sub(r"\s+", " ", tag.get_text(" ", strip=True))
        if 8 <= len(txt) <= 100 and program_keywords.search(txt):
            if subject and subject.lower() in txt.lower():
                if txt not in seen:
                    seen.add(txt)
                    found.insert(0, txt)
            elif txt not in seen:
                seen.add(txt)
                found.append(txt)
        if len(found) >= 12:
            break
    return found[:10]


def _extract_admission_facts(combined_text: str, programs: List[str]) -> Dict[str, Any]:
    """Deterministic extraction of Tuition, IELTS/TOEFL, GPA, Deadlines & Intakes."""
    # 1. Tuition
    tuition_matches: List[str] = []
    if re.search(r"\b(tuition[- ]free|no tuition fees?|zero tuition)\b", combined_text, re.IGNORECASE):
        tuition_matches.append("Tuition-free / No standard tuition fee (semester contribution may apply)")

    currency_pat = re.compile(
        r"(?:tuition|fee|fees|cost)[^.\n]{0,70}?((?:USD|EUR|GBP|CAD|AUD|CHF|\$|€|£)\s?[\d,]{3,6}"
        r"(?:\s?[-–to]+\s?(?:USD|EUR|GBP|CAD|AUD|CHF|\$|€|£)?\s?[\d,]{3,6})?"
        r"(?:\s*(?:per\s*year|annually|/\s*year|per\s*semester|per\s*credit|total))?)",
        re.IGNORECASE
    )
    for m in currency_pat.finditer(combined_text):
        val = re.sub(r"\s+", " ", m.group(1)).strip()
        if val not in tuition_matches:
            tuition_matches.append(val)
        if len(tuition_matches) >= 3:
            break

    # 2. IELTS / TOEFL
    ielts_matches = re.findall(
        r"IELTS[^.\n]{0,45}?(\d(?:\.\d)?(?:\s*(?:overall|band|minimum))?)",
        combined_text,
        re.IGNORECASE
    )
    toefl_matches = re.findall(
        r"TOEFL[^.\n]{0,45}?(\d{2,3}(?:\s*(?:iBT|minimum|total))?)",
        combined_text,
        re.IGNORECASE
    )

    english_reqs: List[str] = []
    if ielts_matches:
        english_reqs.append(f"IELTS: {', '.join(dict.fromkeys(m.strip() for m in ielts_matches[:2]))}")
    if toefl_matches:
        english_reqs.append(f"TOEFL: {', '.join(dict.fromkeys(m.strip() for m in toefl_matches[:2]))}")

    # 3. GPA
    gpa_matches = re.findall(
        r"(?:GPA|CGPA|grade point average)[^.\n]{0,45}?(\d\.\d{1,2}(?:\s*(?:/|out of)\s*\d(?:\.\d)?)?)",
        combined_text,
        re.IGNORECASE
    )
    uk_grade = re.findall(r"\b(First[- ]Class|Upper Second[- ]Class|2:1|2:2)\b", combined_text, re.IGNORECASE)
    gpa_list: List[str] = []
    if gpa_matches:
        gpa_list.extend(dict.fromkeys(g.strip() for g in gpa_matches[:2]))
    if uk_grade:
        gpa_list.extend(dict.fromkeys(u.strip() for u in uk_grade[:2]))

    # 4. Deadlines & Intakes
    intake_matches = re.findall(
        r"\b((?:Fall|Autumn|Winter|Spring|Summer)\s+(?:intake|semester|term|202\d)|(?:September|January|October|April)\s+intake)\b",
        combined_text,
        re.IGNORECASE
    )
    deadline_matches = re.findall(
        r"(?:application\s+)?deadline[s]?[^.\n]{0,75}?((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:,?\s*202\d)?|rolling)",
        combined_text,
        re.IGNORECASE
    )

    return {
        "tuition": tuition_matches if tuition_matches else ["Check official university fee schedule"],
        "english_requirements": english_reqs if english_reqs else ["IELTS / TOEFL proof required (check specific program)"],
        "gpa_requirements": gpa_list if gpa_list else ["Competitive GPA / Bachelor's degree required (check specific program)"],
        "intakes": list(dict.fromkeys(i.strip() for i in intake_matches[:4])) or ["Fall / Winter / Spring (varies by program)"],
        "deadlines": list(dict.fromkeys(d.strip() for d in deadline_matches[:4])) or ["Check official admissions portal for exact cutoff dates"],
        "programs": programs[:8]
    }


# ==========================================
# LangGraph Subgraph: Official Website Admissions Scraper
# ==========================================

class OfficialSiteState(TypedDict):
    university_name: str
    official_url: str
    degree_level: str
    subject: str
    candidate_urls: List[str]
    raw_pages: List[Dict[str, str]]
    programs_found: List[str]
    extracted_admissions: Dict[str, Any]


def resolve_site_node(state: OfficialSiteState) -> Dict[str, Any]:
    """Resolves official university website URL if only name is provided."""
    uni_name = (state.get("university_name") or "").strip()
    url = (state.get("official_url") or "").strip()

    if not url and uni_name:
        known = KNOWN_OFFICIAL_DOMAINS.get(uni_name.lower())
        if known:
            url = known
        else:
            search_hits = search_web_knowledge(f"{uni_name} official website admissions", max_results=3)
            for hit in search_hits:
                candidate = hit.get("url", "")
                if candidate.startswith("http"):
                    url = candidate
                    break

    return {"official_url": url}


def scrape_pages_node(state: OfficialSiteState) -> Dict[str, Any]:
    """Scrapes main university website and discovered admissions/programs subpages in parallel."""
    url = state.get("official_url", "")
    uni_name = state.get("university_name", "")
    subject = state.get("subject", "")
    degree = state.get("degree_level", "MSc")

    raw_pages: List[Dict[str, str]] = []
    programs_found: List[str] = []
    subpages: List[str] = []

    if url:
        main_html = _fetch_html(url)
        if main_html:
            raw_pages.append({"url": url, "text": _clean_text(main_html)})
            programs_found.extend(_extract_programs_from_html(main_html, subject=subject))
            subpages = _discover_subpages(url, main_html, max_links=3)

            if subpages:
                with ThreadPoolExecutor(max_workers=3) as executor:
                    futures = {executor.submit(_fetch_html, sp): sp for sp in subpages}
                    for fut, sp_url in futures.items():
                        sub_html = fut.result()
                        if sub_html:
                            raw_pages.append({"url": sp_url, "text": _clean_text(sub_html)})
                            programs_found.extend(_extract_programs_from_html(sub_html, subject=subject))

    # Parallel search fallback for JS-heavy sites or blocked bots
    domain_filter = ""
    if url:
        parsed = urllib.parse.urlparse(url)
        if parsed.netloc:
            domain_filter = f"site:{parsed.netloc} "

    search_q = f"{domain_filter}{uni_name} {degree} {subject} tuition IELTS TOEFL GPA deadline intake".strip()
    web_snippets = search_web_knowledge(search_q, max_results=4)
    snippet_text = " ".join(f"{w.get('title', '')} {w.get('snippet', '')}" for w in web_snippets)
    if snippet_text.strip():
        raw_pages.append({"url": "web_search_fallback", "text": snippet_text})

    # Deduplicate programs
    dedup_programs = list(dict.fromkeys(programs_found))
    return {
        "candidate_urls": [url] + subpages if url else [],
        "raw_pages": raw_pages,
        "programs_found": dedup_programs[:10]
    }


def extract_admissions_node(state: OfficialSiteState) -> Dict[str, Any]:
    """Extracts structured tuition, IELTS/TOEFL, GPA, deadlines, intakes, and programs."""
    raw_pages = state.get("raw_pages", [])
    programs = state.get("programs_found", [])
    combined_text = " ".join(p.get("text", "") for p in raw_pages)

    facts = _extract_admission_facts(combined_text, programs)
    facts["university_name"] = state.get("university_name") or state.get("official_url")
    facts["official_url"] = state.get("official_url", "")
    facts["pages_scraped"] = [p.get("url") for p in raw_pages if p.get("url") != "web_search_fallback"]

    return {"extracted_admissions": facts}


def build_official_site_subgraph():
    builder = StateGraph(OfficialSiteState)
    builder.add_node("resolve_site", resolve_site_node)
    builder.add_node("scrape_pages", scrape_pages_node)
    builder.add_node("extract_admissions", extract_admissions_node)

    builder.add_edge(START, "resolve_site")
    builder.add_edge("resolve_site", "scrape_pages")
    builder.add_edge("scrape_pages", "extract_admissions")
    builder.add_edge("extract_admissions", END)
    return builder.compile()


official_site_subgraph = build_official_site_subgraph()


def scrape_official_university_admissions(
    university_name: str = "",
    official_url: str = "",
    degree_level: str = "MSc",
    subject: str = "Computer Science"
) -> Dict[str, Any]:
    """
    Runs the compiled LangGraph subgraph to scrape a university's main website and
    extract tuition, IELTS/TOEFL, GPA, deadlines/intakes, and degree programs.
    """
    try:
        res = official_site_subgraph.invoke({
            "university_name": university_name,
            "official_url": official_url,
            "degree_level": degree_level,
            "subject": subject,
            "candidate_urls": [],
            "raw_pages": [],
            "programs_found": [],
            "extracted_admissions": {}
        })
        return {
            "success": True,
            "data": res.get("extracted_admissions", {})
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "data": {}
        }
