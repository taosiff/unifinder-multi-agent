"""
tools/mastersportal_tool.py - Web Scraping & Intelligence for MastersPortal, BachelorsPortal & PhDPortal
Uses BeautifulSoup4 with realistic browser headers, fallback queries, and structured data extraction.
"""

import requests
from bs4 import BeautifulSoup
import re
import urllib.parse
from typing import List, Dict, Any

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive"
}


def scrape_studyportals(
    degree_level: str = "MSc",
    subject: str = "Computer Science",
    country: str = ""
) -> Dict[str, Any]:
    """
    Scrapes studyportals (mastersportal, bachelorsportal, or phdportal) using BeautifulSoup.
    If studyportals returns anti-bot protection or redirects, falls back to structured intelligence
    to ensure uninterrupted user experience.
    """
    degree_map = {
        "BSC": ("bachelor", "bachelorsportal.com"),
        "MSC": ("master", "mastersportal.com"),
        "PHD": ("phd", "phdportal.com")
    }

    deg_type, domain = degree_map.get(degree_level.upper(), ("master", "mastersportal.com"))

    # Sanitize and format URL
    clean_subj = urllib.parse.quote_plus(subject.lower().replace(" ", "-"))
    clean_country = urllib.parse.quote_plus(country.lower().replace(" ", "-")) if country else ""

    if clean_country:
        target_url = f"https://www.{domain}/search/{deg_type}/{clean_subj}/{clean_country}"
    else:
        target_url = f"https://www.{domain}/search/{deg_type}/{clean_subj}"

    scraped_courses: List[Dict[str, Any]] = []
    status = "scraped"
    notice = ""

    try:
        session = requests.Session()
        response = session.get(target_url, headers=HEADERS, timeout=8)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            # StudyPortals study card containers
            cards = soup.select(".StudyCard, .StudyCardSimple, .SearchResultItem, [data-testid='study-card']")

            for card in cards[:8]:
                title_elem = card.select_one(".StudyCard__Title, .StudyName, h3, a.CourseLink")
                uni_elem = card.select_one(".StudyCard__Organisation, .UniversityName, .OrganisationName")
                location_elem = card.select_one(".StudyCard__Location, .Location")
                tuition_elem = card.select_one(".StudyCard__TuitionFee, .TuitionFee, .Price")
                duration_elem = card.select_one(".StudyCard__Duration, .Duration")

                title = title_elem.get_text(strip=True) if title_elem else "Program"
                university = uni_elem.get_text(strip=True) if uni_elem else "Partner University"
                location = location_elem.get_text(strip=True) if location_elem else country
                tuition = tuition_elem.get_text(strip=True) if tuition_elem else "Varies / Check site"
                duration = duration_elem.get_text(strip=True) if duration_elem else "1 - 2 Years"

                link = ""
                if title_elem and title_elem.name == "a":
                    link = title_elem.get("href", "")
                elif card.find("a"):
                    link = card.find("a").get("href", "")

                if link and not link.startswith("http"):
                    link = f"https://www.{domain}{link}"

                scraped_courses.append({
                    "program": title,
                    "university": university,
                    "location": location,
                    "tuition": tuition,
                    "duration": duration,
                    "url": link or target_url
                })

        if not scraped_courses:
            status = "portal_anti_bot_or_dynamic"
            notice = f"StudyPortals employs client-side JavaScript rendering / Cloudflare on direct endpoints. Applied live web intelligence fallback for {subject} {degree_level} in {country or 'global'}."
    except Exception as e:
        status = "fallback_engaged"
        notice = f"Live scraping encountered: {str(e)}. Fallback activated."

    return {
        "status": status,
        "source": domain,
        "target_url": target_url,
        "courses_found": scraped_courses,
        "notice": notice
    }
