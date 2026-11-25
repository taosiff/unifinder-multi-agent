"""
tools/univs_tool.py - Univs.com Catalogue API & MCP Integration Tool
Searches 22,943+ institutes and 256,464+ programmes across 62 countries.
Runs in parallel alongside MastersPortal and web search tools.
"""

import requests
from typing import Dict, Any, List, Optional

UNIVS_ADDRESSES = {
    "rest_api_base": "https://univs.com/wp-json/univs-agent/v1",
    "mcp_server": "https://univs.com/wp-json/univs-agent/v1/mcp",
    "openapi_description": "https://univs.com/.well-known/openapi.json",
    "mcp_server_card": "https://univs.com/.well-known/mcp.json",
    "short_guide_llms": "https://univs.com/llms.txt",
    "full_guide_llms": "https://univs.com/llms-full.txt",
    "assistants_setup": "https://univs.com/ai-assistants/",
    "api_terms": "https://univs.com/api-terms/"
}

DEGREE_MAP = {
    "bsc": "bachelor",
    "bachelor": "bachelor",
    "undergraduate": "bachelor",
    "msc": "master",
    "master": "master",
    "graduate": "master",
    "phd": "doctorate",
    "doctorate": "doctorate",
    "doctoral": "doctorate",
    "diploma": "diploma",
    "certificate": "certificate",
    "foundation": "foundation"
}

DEFAULT_HEADERS = {
    "User-Agent": "UniFinderAI/2.6.0 (Higher-Ed Multi-Agent Assistant)",
    "Accept": "application/json"
}


def get_univs_addresses() -> Dict[str, str]:
    """Returns all official Univs.com REST API, MCP, and LLM documentation addresses."""
    return UNIVS_ADDRESSES


def search_univs_programs(
    query: str,
    country: str = "",
    degree_level: str = "MSc",
    scholarship_only: bool = False,
    page: int = 1,
    limit: int = 8
) -> Dict[str, Any]:
    """
    Search study programmes on the Univs.com public catalogue API.
    """
    api_url = f"{UNIVS_ADDRESSES['rest_api_base']}/programs"
    mapped_degree = DEGREE_MAP.get(degree_level.strip().lower(), "master") if degree_level else ""

    params: Dict[str, Any] = {
        "q": query.strip() if query else "Computer Science",
        "page": page
    }
    if country:
        params["country"] = country.strip()
    if mapped_degree:
        params["degree"] = mapped_degree
    if scholarship_only:
        params["scholarship"] = "1"

    try:
        resp = requests.get(api_url, params=params, headers=DEFAULT_HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_results = data.get("results", [])
            programs = []
            for item in raw_results[:limit]:
                inst = item.get("institute") or {}
                programs.append({
                    "id": item.get("id"),
                    "program_name": item.get("name"),
                    "url": item.get("url"),
                    "university_name": inst.get("name", "Unknown Institution"),
                    "university_url": inst.get("url", ""),
                    "country": inst.get("country", country or "Global"),
                    "city": inst.get("city", ""),
                    "degree": ", ".join(item.get("degree", [degree_level])),
                    "disciplines": item.get("disciplines", []),
                    "duration": item.get("duration", "Not specified"),
                    "scholarship_available": bool(item.get("scholarship", False)),
                    "source": "Univs.com Catalogue API"
                })
            return {
                "success": True,
                "source": "Univs.com Public Catalogue",
                "total_available": data.get("total", len(programs)),
                "programs": programs
            }
        return {
            "success": False,
            "error": f"Univs API returned HTTP {resp.status_code}",
            "programs": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "programs": []
        }


def search_univs_institutes(
    query: str,
    country: str = "",
    page: int = 1,
    limit: int = 6
) -> Dict[str, Any]:
    """
    Search universities and institutes on the Univs.com public catalogue API.
    """
    api_url = f"{UNIVS_ADDRESSES['rest_api_base']}/institutes"
    params: Dict[str, Any] = {
        "q": query.strip() if query else "",
        "page": page
    }
    if country:
        params["country"] = country.strip()

    try:
        resp = requests.get(api_url, params=params, headers=DEFAULT_HEADERS, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            raw_results = data.get("results", [])
            institutes = []
            for item in raw_results[:limit]:
                institutes.append({
                    "id": item.get("id"),
                    "name": item.get("name"),
                    "url": item.get("url"),
                    "programs_url": item.get("programs_url"),
                    "country": item.get("country", ""),
                    "city": item.get("city", ""),
                    "type": item.get("type", "University"),
                    "founded": item.get("founded", ""),
                    "program_count": item.get("program_count", 0),
                    "scholarships": bool(item.get("scholarships", False)),
                    "source": "Univs.com Catalogue API"
                })
            return {
                "success": True,
                "source": "Univs.com Public Catalogue",
                "total_available": data.get("total", len(institutes)),
                "institutes": institutes
            }
        return {
            "success": False,
            "error": f"Univs API returned HTTP {resp.status_code}",
            "institutes": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "institutes": []
        }
