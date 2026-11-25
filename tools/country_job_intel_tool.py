"""
tools/country_job_intel_tool.py - Country Economics/Student-Friendliness & Subject Job/Sponsored-Visa Intelligence
Provides live + structured data for:
  1. Country Economics, PR & Student-Friendliness Agent
  2. Subject Job Market & Post-Study Sponsored Visa Agent
"""

from typing import Any, Dict, List
from tools.web_intelligence import search_web_knowledge
from tools.pr_visa_tool import evaluate_immigration_pathway

COUNTRY_ECONOMY_PROFILES: Dict[str, Dict[str, Any]] = {
    "germany": {
        "economy_overview": "Europe's largest economy (#3 globally). Strong manufacturing, automotive, AI, and engineering sectors with low unemployment (~3.4%–6.0%).",
        "part_time_work_rights": "140 full days or 280 half days per year; minimum wage €12.82/hr (~€1,000+/mo part-time).",
        "student_friendliness": "Very High (9/10) — Public universities are tuition-free, discounted Deutschlandticket (€58/mo) transit, strong student unions, high safety.",
        "english_in_daily_life": "High in major cities (Berlin, Munich, Frankfurt) & tech offices; B1 German strongly boosts daily life & PR speed."
    },
    "canada": {
        "economy_overview": "G7 resource & tech-service economy. Strong AI/software hubs in Toronto, Vancouver, and Montreal; moderate inflation and housing costs.",
        "part_time_work_rights": "Up to 24 hours/week off-campus during semesters, full-time during scheduled breaks.",
        "student_friendliness": "Very High (9/10) — Multicultural, welcoming to immigrants, clear PGWP-to-PR bridge.",
        "english_in_daily_life": "Native English (French in Quebec)."
    },
    "united states": {
        "economy_overview": "World's largest economy & tech/finance innovation hub. Highest graduate salaries globally, especially in AI, Software, and Biotech.",
        "part_time_work_rights": "Up to 20 hours/week on-campus during semesters; CPT/OPT for off-campus internships.",
        "student_friendliness": "High on Campus (8/10) — World-class campus facilities & funding, though healthcare & tuition require insurance/budgeting.",
        "english_in_daily_life": "Native English."
    },
    "united kingdom": {
        "economy_overview": "Major global finance, fintech, AI, and life-sciences hub (London, Cambridge, Manchester, Edinburgh).",
        "part_time_work_rights": "Up to 20 hours/week during term time, full-time during holidays.",
        "student_friendliness": "High (8.5/10) — 1-year Master's degrees save living costs, NHS healthcare access via IHS, vibrant international campuses.",
        "english_in_daily_life": "Native English."
    },
    "australia": {
        "economy_overview": "Resilient APAC economy with strong tech, mining-tech, healthcare, and civil engineering demand; high minimum wage (~AUD $24.10/hr).",
        "part_time_work_rights": "48 hours per fortnight during study terms, unlimited during breaks.",
        "student_friendliness": "High (8.5/10) — High quality of life, sunny climate, strong student protections, regional PR bonuses.",
        "english_in_daily_life": "Native English."
    },
    "netherlands": {
        "economy_overview": "High-income European trade, semiconductor (ASML), and fintech hub with very low unemployment.",
        "part_time_work_rights": "Up to 16 hours/week with employer work permit (or full-time June–August).",
        "student_friendliness": "Very High (9/10) — Over 2,000 English-taught programs, cycling culture, 90%+ English fluency nationwide.",
        "english_in_daily_life": "Near-native English proficiency everywhere."
    }
}

SPONSORED_VISA_PROFILES: Dict[str, Dict[str, Any]] = {
    "germany": {
        "sponsored_visa_name": "EU Blue Card / Skilled Worker Residence Permit",
        "sponsorship_difficulty": "Low (Employer-Friendly)",
        "key_rules": "No labor market test required. Employer simply issues a qualifying job contract (€41k–€45.3k/yr for shortage/STEM roles).",
        "job_search_window": "18-Month Job Seeker Residence Permit after graduation"
    },
    "canada": {
        "sponsored_visa_name": "PGWP → Express Entry (CEC) / Provincial Nominee (PNP)",
        "sponsorship_difficulty": "Low to Moderate",
        "key_rules": "PGWP is an open work permit (up to 3 years) — employers do NOT need LMIA sponsorship to hire you after graduation!",
        "job_search_window": "Up to 3 years open work permit"
    },
    "united states": {
        "sponsored_visa_name": "F-1 OPT / 36-Month STEM OPT → H-1B Visa",
        "sponsorship_difficulty": "High (H-1B Lottery)",
        "key_rules": "STEM grads get 3 years of OPT without H-1B sponsorship, giving 3 annual lottery attempts. Cap-exempt universities/research labs bypass the lottery.",
        "job_search_window": "12 months OPT (+24 months STEM extension)"
    },
    "united kingdom": {
        "sponsored_visa_name": "2-Year Graduate Route → Skilled Worker Visa",
        "sponsorship_difficulty": "Moderate",
        "key_rules": "Must find a Home Office licensed sponsor. 'New Entrant' discount lowers salary threshold to ~£30,960/yr (or £38,700 standard).",
        "job_search_window": "2 years (3 years for PhD)"
    },
    "australia": {
        "sponsored_visa_name": "Subclass 485 Temporary Graduate → 189/190/482",
        "sponsorship_difficulty": "Moderate",
        "key_rules": "Full work rights on 485 visa (2–4 years). Skilled independent (189) & state nominated (190) PR do not require employer sponsorship.",
        "job_search_window": "2 to 4 years post-study"
    },
    "netherlands": {
        "sponsored_visa_name": "Zoekjaar (Orientation Year) → Highly Skilled Migrant (Kennismigrant)",
        "sponsorship_difficulty": "Low to Moderate",
        "key_rules": "Reduced salary threshold (~€2,801/mo gross) if hired within 3 years of graduation by an IND-recognized sponsor.",
        "job_search_window": "1-year Orientation Year permit"
    }
}


def fetch_country_student_intelligence(country: str) -> Dict[str, Any]:
    """
    Agent Tool 1: Gathers Country Economics, PR Info, and Student-Friendliness.
    Combines structured country benchmarks, PR pathway data, and live web search.
    """
    target = (country or "Germany").strip()
    key = target.lower()

    profile = COUNTRY_ECONOMY_PROFILES.get(key, {
        "economy_overview": f"Developing/established international study destination ({target}). Check current GDP & local job stability.",
        "part_time_work_rights": "Typically 15–20 hours/week for international students during term.",
        "student_friendliness": "Check campus international office & local living safety index.",
        "english_in_daily_life": "Varies by city; check university language requirements."
    })

    pr_info = evaluate_immigration_pathway(target)
    live_econ = search_web_knowledge(f"{target} economy international student friendly part time work PR 2025 2026", max_results=3)

    return {
        "country": target,
        "economy_overview": profile["economy_overview"],
        "part_time_work_rights": profile["part_time_work_rights"],
        "student_friendliness": profile["student_friendliness"],
        "english_in_daily_life": profile["english_in_daily_life"],
        "pr_summary": f"{pr_info.get('pr_feasibility')} Feasibility — {pr_info.get('pr_pathway')} ({pr_info.get('pr_timeline')})",
        "live_web_insights": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:200], "url": r.get("url", "")}
            for r in live_econ[:2]
        ]
    }


def fetch_subject_job_market_intel(country: str, subject: str, degree_level: str = "MSc") -> Dict[str, Any]:
    """
    Agent Tool 2: Gathers Subject Job Conditions, Hiring Demand, and After-Study Sponsored Visa Reality.
    """
    target_country = (country or "Germany").strip()
    target_subject = (subject or "Computer Science").strip()
    key = target_country.lower()

    visa_profile = SPONSORED_VISA_PROFILES.get(key, {
        "sponsored_visa_name": "Post-Study Work Permit → Employer-Sponsored Skilled Visa",
        "sponsorship_difficulty": "Moderate (Check local labor market test rules)",
        "key_rules": "Verify minimum graduate salary thresholds and licensed sponsor registries.",
        "job_search_window": "12–24 months (varies by country)"
    })

    live_jobs = search_web_knowledge(
        f"{target_subject} job market demand {target_country} international graduate visa sponsorship salary 2025 2026",
        max_results=3
    )

    return {
        "country": target_country,
        "subject": target_subject,
        "degree_level": degree_level,
        "sponsored_visa_name": visa_profile["sponsored_visa_name"],
        "sponsorship_difficulty": visa_profile["sponsorship_difficulty"],
        "sponsorship_rules": visa_profile["key_rules"],
        "job_search_window": visa_profile["job_search_window"],
        "live_job_market_insights": [
            {"title": r.get("title", ""), "snippet": r.get("snippet", "")[:220], "url": r.get("url", "")}
            for r in live_jobs[:3]
        ]
    }
