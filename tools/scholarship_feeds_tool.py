"""
tools/scholarship_feeds_tool.py - Attribution-Compliant Scholarship Feed Aggregator
Integrates:
  - Worldwide Scholarships (RSS): https://worldwide-scholarships.com/rss.xml
  - Open Scholarships (JSON, CC-BY-4.0): https://scholarships.grudged.io/scholarships.json
Stores factual metadata only, preserves source attribution, links to original postings,
and distinguishes between 'Newly Discovered' and 'Verified Open' records.
"""

import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

import requests

WORLDWIDE_RSS_URL = "https://worldwide-scholarships.com/rss.xml"
OPEN_SCHOLARSHIPS_JSON_URL = "https://scholarships.grudged.io/scholarships.json"

HEADERS = {
    "User-Agent": "UniFinderAI/2.6.0 (Educational Assistant; factual metadata + attribution)",
    "Accept": "application/json, application/xml, text/xml, */*"
}

SCHOLARSHIP_SOURCES_CATALOGUE = [
    {
        "source": "Worldwide Scholarships",
        "integration": "RSS",
        "global_coverage": "International",
        "url": WORLDWIDE_RSS_URL,
        "attribution": "Worldwide Scholarships (factual fields & link to original posting)"
    },
    {
        "source": "Open Scholarships",
        "integration": "JSON",
        "global_coverage": "Nevada-focused (US)",
        "url": OPEN_SCHOLARSHIPS_JSON_URL,
        "attribution": "Open Scholarships by Grudged LLC - https://github.com/Grudged/open-scholarships (CC BY 4.0)"
    },
    {
        "source": "ScholarshipHunter",
        "integration": "Open-source ingestion code",
        "global_coverage": "International",
        "url": "https://github.com/topics/scholarship-scraper",
        "attribution": "Open-source ingestion patterns"
    },
    {
        "source": "Scholarship Radar",
        "integration": "Open-source crawler",
        "global_coverage": "Selected global sources",
        "url": "https://github.com/topics/scholarships",
        "attribution": "Open-source crawler patterns"
    },
    {
        "source": "Official university portals",
        "integration": "RSS / crawling",
        "global_coverage": "Worldwide",
        "url": "",
        "attribution": "Direct official university admissions & financial aid pages"
    },
    {
        "source": "Government scholarship portals",
        "integration": "RSS / crawling / APIs",
        "global_coverage": "Country-specific",
        "url": "",
        "attribution": "Official national government scholarship agencies (DAAD, Fulbright, Chevening, MEXT, etc.)"
    }
]

# 15-minute TTL cache to respect source servers
_CACHE: Dict[str, Any] = {
    "rss": {"ts": 0.0, "data": []},
    "json": {"ts": 0.0, "data": []}
}
CACHE_TTL_SECONDS = 900


def _infer_degrees(text: str) -> List[str]:
    low = text.lower()
    degs = []
    if any(k in low for k in ("bachelor", "undergraduate", "bsc", "high-school")):
        degs.append("BSc")
    if any(k in low for k in ("master", "msc", "graduate", "postgraduate")):
        degs.append("MSc")
    if any(k in low for k in ("phd", "doctorate", "doctoral")):
        degs.append("PhD")
    return degs or ["BSc", "MSc", "PhD"]


def _infer_destination(text: str) -> str:
    low = text.lower()
    mapping = [
        ("germany", "Germany"),
        ("uk ", "United Kingdom"),
        ("united kingdom", "United Kingdom"),
        ("chevening", "United Kingdom"),
        ("usa", "United States"),
        ("united states", "United States"),
        ("fulbright", "United States"),
        ("canada", "Canada"),
        ("australia", "Australia"),
        ("europe", "European Union"),
        ("erasmus", "European Union"),
        ("japan", "Japan"),
        ("mext", "Japan"),
        ("china", "China"),
        ("france", "France"),
        ("italy", "Italy"),
        ("netherlands", "Netherlands"),
    ]
    for kw, dest in mapping:
        if kw in low:
            return dest
    return "International"


def fetch_worldwide_scholarships_rss(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches factual scholarship metadata from Worldwide Scholarships RSS feed.
    Preserves attribution and links to the original posting without republishing full articles.
    """
    now = time.time()
    if _CACHE["rss"]["data"] and (now - _CACHE["rss"]["ts"] < CACHE_TTL_SECONDS):
        return _CACHE["rss"]["data"][:limit]

    records: List[Dict[str, Any]] = []
    try:
        resp = requests.get(WORLDWIDE_RSS_URL, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            for idx, item in enumerate(root.findall(".//item")[:20]):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub_date = (item.findtext("pubDate") or "").strip()
                cats = [c.text.strip() for c in item.findall("category") if c.text]

                combined = f"{title} {' '.join(cats)}"
                records.append({
                    "id": f"wws-rss-{idx}",
                    "title": title,
                    "destination": _infer_destination(combined),
                    "degree_levels": _infer_degrees(combined),
                    "funding_type": "International Scholarship / Guide",
                    "coverage": "Factual listing — check original posting for exact award terms",
                    "eligibility": f"Tags: {', '.join(cats[:4])}" if cats else "International applicants",
                    "deadline": f"Published: {pub_date[:16]}" if pub_date else "See original posting",
                    "status": "Active",
                    "record_status": "Newly Discovered",
                    "official_url": link,
                    "source_name": "Worldwide Scholarships (RSS)",
                    "attribution": "Worldwide Scholarships — linked to original posting"
                })
            _CACHE["rss"] = {"ts": now, "data": records}
    except Exception:
        pass

    return records[:limit]


def fetch_open_scholarships_json(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Fetches factual scholarship records from Open Scholarships JSON (CC-BY-4.0).
    Preserves required CC-BY-4.0 attribution and distinguishes 'Verified Open' vs 'Newly Discovered'.
    """
    now = time.time()
    if _CACHE["json"]["data"] and (now - _CACHE["json"]["ts"] < CACHE_TTL_SECONDS):
        return _CACHE["json"]["data"][:limit]

    records: List[Dict[str, Any]] = []
    try:
        resp = requests.get(OPEN_SCHOLARSHIPS_JSON_URL, headers=HEADERS, timeout=8)
        if resp.status_code == 200:
            payload = resp.json()
            meta = payload.get("meta", {})
            attribution = meta.get(
                "attribution_required",
                "Open Scholarships by Grudged LLC - https://github.com/Grudged/open-scholarships (CC BY 4.0)"
            )
            for item in payload.get("results", [])[:25]:
                award = item.get("award") or {}
                amt_max = award.get("amount_max")
                currency = award.get("currency", "USD")
                basis = (award.get("basis") or "Merit/Need").title()
                coverage_str = f"Up to {amt_max:,} {currency}" if amt_max else (award.get("notes") or "See official posting")

                dl = item.get("deadline") or {}
                dl_str = dl.get("date") or (dl.get("type", "varies").title())

                links = item.get("links") or {}
                orig_url = links.get("apply_url") or links.get("info_url") or "https://scholarships.grudged.io/"

                elig = item.get("eligibility") or {}
                edu_levels = " ".join(elig.get("education_level", []))
                gpa_min = elig.get("gpa_min")
                elig_str = f"Sponsor: {item.get('sponsor', 'State/Org')}"
                if gpa_min:
                    elig_str += f" | Min GPA: {gpa_min}"

                avail = (item.get("availability") or "unknown").lower()
                rec_status = "Verified Open" if avail == "open" else "Newly Discovered"

                records.append({
                    "id": f"open-json-{item.get('id', len(records))}",
                    "title": item.get("name", "Scholarship"),
                    "destination": "United States (Nevada)",
                    "degree_levels": _infer_degrees(edu_levels),
                    "funding_type": basis,
                    "coverage": coverage_str,
                    "eligibility": elig_str,
                    "deadline": str(dl_str),
                    "status": (item.get("status") or "active").title(),
                    "record_status": rec_status,
                    "official_url": orig_url,
                    "source_name": "Open Scholarships (JSON)",
                    "attribution": attribution
                })
            _CACHE["json"] = {"ts": now, "data": records}
    except Exception:
        pass

    return records[:limit]


def fetch_all_scholarship_feeds(rss_limit: int = 6, json_limit: int = 6) -> List[Dict[str, Any]]:
    """Fetches Worldwide Scholarships RSS and Open Scholarships JSON in parallel."""
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_rss = executor.submit(fetch_worldwide_scholarships_rss, rss_limit)
        f_json = executor.submit(fetch_open_scholarships_json, json_limit)
        rss_items = f_rss.result()
        json_items = f_json.result()
    return rss_items + json_items
