"""
tools/reviews_tool.py - Student & Alumni Reviews Extractor (Reddit RSS + Web Forums + Alumni DB)
100% free, zero-API-key student review intelligence for selected universities and programs.
"""

import xml.etree.ElementTree as ET
from typing import Any, Dict, List
import requests

from tools.web_intelligence import search_web_knowledge

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}


def _fetch_reddit_rss(query: str, limit: int = 4) -> List[Dict[str, Any]]:
    """Attempts to fetch public Reddit RSS search results (no API key required)."""
    reviews: List[Dict[str, Any]] = []
    try:
        resp = requests.get(
            "https://www.reddit.com/search.rss",
            params={"q": query, "sort": "relevance"},
            headers=HEADERS,
            timeout=6
        )
        if resp.status_code == 200 and "<feed" in resp.text:
            root = ET.fromstring(resp.text)
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            for entry in root.findall("atom:entry", ns)[:limit]:
                title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
                link_el = entry.find("atom:link", ns)
                url = link_el.attrib.get("href", "") if link_el is not None else ""
                if title:
                    reviews.append({
                        "source": "Reddit (RSS)",
                        "title": title,
                        "url": url,
                        "snippet": "Community discussion thread on Reddit"
                    })
    except Exception:
        pass
    return reviews


def fetch_university_reviews(
    universities: List[Dict[str, Any]],
    degree_level: str = "MSc",
    subject: str = "Computer Science"
) -> List[Dict[str, Any]]:
    """
    Extracts student & alumni reviews for the selected universities/programs from:
      1. Reddit public RSS (if accessible)
      2. DuckDuckGo student forum & Reddit search
      3. Curated alumni satisfaction & review highlights
    """
    compiled_reviews: List[Dict[str, Any]] = []

    for uni in universities[:3]:
        uni_name = uni.get("name", "")
        if not uni_name:
            continue

        query = f"{uni_name} {degree_level} {subject} student review reddit"
        reddit_posts = _fetch_reddit_rss(f"{uni_name} {subject}", limit=2)
        web_reviews = search_web_knowledge(query, max_results=3)

        highlights = []
        for rp in reddit_posts:
            highlights.append(f"[Reddit] {rp['title']} ({rp['url']})")
        for wr in web_reviews[:2]:
            snippet = (wr.get("snippet") or "")[:180]
            if snippet:
                highlights.append(f"[{wr.get('title', 'Student Forum')}]: {snippet}")

        compiled_reviews.append({
            "university_name": uni_name,
            "satisfaction_rating": uni.get("student_satisfaction_rating", "N/A"),
            "alumni_summary": uni.get("alumni_reviews", ""),
            "community_threads": highlights[:4]
        })

    return compiled_reviews
