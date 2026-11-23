"""
tools/opportunities_tool.py - Live Global Scholarships, Deadlines Calendar & Immigration News
Maintains curated active scholarships and live DuckDuckGo query updates for newly announced grants.
"""

from typing import List, Dict, Any, Optional
from tools.web_intelligence import search_web_knowledge

ACTIVE_GLOBAL_SCHOLARSHIPS = [
    {
        "id": "daad-epos",
        "title": "DAAD Development-Related Postgraduate Courses (EPOS)",
        "destination": "Germany",
        "degree_levels": ["MSc", "PhD"],
        "funding_type": "Fully Funded",
        "coverage": "Full tuition waiver, €934/month stipend (€1,300 for PhD), health insurance, travel allowance.",
        "eligibility": "Bachelor's degree with minimum 2 years of relevant professional work experience.",
        "deadline": "August - December (Varies by university course)",
        "status": "Active / Annual Cycles",
        "official_url": "https://www.daad.de/en/study-and-research-in-germany/scholarships/"
    },
    {
        "id": "erasmus-mundus",
        "title": "Erasmus Mundus Joint Master Degrees (EMJMD)",
        "destination": "European Union (Study in 2-3 EU countries)",
        "degree_levels": ["MSc"],
        "funding_type": "Fully Funded",
        "coverage": "Full tuition participation cost, €1,400/month living allowance, installation & travel grants.",
        "eligibility": "High academic standing in Bachelor's degree, strong SOP, no previous Erasmus grant.",
        "deadline": "November 15 - January 15 (Annual)",
        "status": "Active",
        "official_url": "https://www.eacea.ec.europa.eu/scholarships/erasmus-mundus-catalogue_en"
    },
    {
        "id": "fulbright-student",
        "title": "Fulbright Foreign Student Program",
        "destination": "United States",
        "degree_levels": ["MSc", "PhD"],
        "funding_type": "Fully Funded",
        "coverage": "Full tuition, living stipend, roundtrip airfare, health benefit plan, J-1 visa sponsorship.",
        "eligibility": "Outstanding academic record, leadership potential, country-specific citizen requirements.",
        "deadline": "February - May (Varies by US Embassy / Commission in home country)",
        "status": "Active",
        "official_url": "https://foreign.fulbrightonline.org"
    },
    {
        "id": "chevening",
        "title": "UK Chevening Scholarships",
        "destination": "United Kingdom",
        "degree_levels": ["MSc"],
        "funding_type": "Fully Funded",
        "coverage": "Full tuition fees for 1-year master's, monthly living allowance, return flights, arrival allowance.",
        "eligibility": "Minimum 2 years (2,800 hours) work experience, return to home country for 2 years minimum.",
        "deadline": "Early November (Opens August each year)",
        "status": "Active",
        "official_url": "https://www.chevening.org/scholarships/"
    },
    {
        "id": "mext-japan",
        "title": "Japanese Government MEXT Research Scholarships",
        "destination": "Japan",
        "degree_levels": ["MSc", "PhD"],
        "funding_type": "Fully Funded",
        "coverage": "Full university tuition waiver, 144,000 JPY/month stipend, round-trip flight ticket.",
        "eligibility": "Under 35 years old, bachelor's degree holder, willing to learn basic Japanese.",
        "deadline": "April - June (Embassy Track) / October (University Track)",
        "status": "Active",
        "official_url": "https://www.studyinjapan.go.jp/en/planning/scholarship/"
    },
    {
        "id": "csc-china",
        "title": "Chinese Government Scholarship (CSC - High Level Postgraduate)",
        "destination": "China",
        "degree_levels": ["MSc", "PhD"],
        "funding_type": "Fully Funded",
        "coverage": "Full tuition, on-campus accommodation, comprehensive medical insurance, 3,000 - 3,500 RMB/month.",
        "eligibility": "Non-Chinese citizen, under 35 for Master's, under 40 for PhD.",
        "deadline": "December - April (Annual)",
        "status": "Active",
        "official_url": "https://www.campuschina.org"
    },
    {
        "id": "australia-awards",
        "title": "Australia Awards Scholarships",
        "destination": "Australia",
        "degree_levels": ["MSc", "PhD"],
        "funding_type": "Fully Funded",
        "coverage": "Full tuition fees, return air travel, establishment allowance, contribution to living expenses (CLE).",
        "eligibility": "Citizens of participating Indo-Pacific and partner nations.",
        "deadline": "April 30 (Annual)",
        "status": "Active",
        "official_url": "https://www.dfat.gov.au/people-to-people/australia-awards"
    },
    {
        "id": "eiffel-france",
        "title": "French Government Eiffel Excellence Scholarship",
        "destination": "France",
        "degree_levels": ["MSc", "PhD"],
        "funding_type": "High Merit Partial/Full",
        "coverage": "€1,181/month allowance (Master's) or €1,700/month (PhD), international transport, health insurance.",
        "eligibility": "Non-French nationality, under 27 for Master's, nominated directly by French institution.",
        "deadline": "Early January (Annual)",
        "status": "Active",
        "official_url": "https://www.campusfrance.org/en/eiffel-scholarship-program-of-excellence"
    },
    {
        "id": "dsu-italy",
        "title": "Italian Regional DSU / EDISU Scholarships",
        "destination": "Italy",
        "degree_levels": ["BSc", "MSc"],
        "funding_type": "Need & Merit Based",
        "coverage": "100% tuition exemption, free campus cafeteria meals, plus up to €6,500 - €7,000 cash grant per year.",
        "eligibility": "Family income assessment (ISEE Parificato < ~€25,000).",
        "deadline": "July - September (Varies by region: Tuscany, Piedmont, Lombardy)",
        "status": "Active",
        "official_url": "https://www.universitaly.it"
    }
]

IMMIGRATION_AND_STUDY_NEWS = [
    {
        "id": "news-canada-cap",
        "title": "Canada IRCC Study Permit Caps: Priority for Master's and PhD Applicants",
        "date": "2024-2026 Policy Notice",
        "category": "Visa Policy",
        "country": "Canada",
        "summary": "Master's and PhD graduates remain eligible for 3-year PGWP regardless of course duration, and are prioritized in federal allocations.",
        "impact": "Favorable for graduate research students; college diplomas face stricter quotas."
    },
    {
        "id": "news-germany-chancenkarte",
        "title": "Germany Launches Opportunity Card (Chancenkarte) for International Graduates",
        "date": "2024-2026 Policy Notice",
        "category": "Immigration & PR",
        "country": "Germany",
        "summary": "Points-based entry card allows international talents with recognized foreign degrees to enter Germany to search for skilled employment. EU Blue Card fast-track PR confirmed at 21 months with B1 German.",
        "impact": "Unlocks Europe's most accessible graduate settlement pathway."
    },
    {
        "id": "news-uk-new-entrant",
        "title": "UK Skilled Worker Visa: Reduced Salary Threshold for International Graduates",
        "date": "2024-2026 Policy Notice",
        "category": "Work Rights",
        "country": "United Kingdom",
        "summary": "While general Skilled Worker salary threshold rose to £38,700, the 'New Entrant' concession applies to student visa switchers under 26, lowering required salary to ~£30,960/yr.",
        "impact": "Graduates on 2-year Graduate Route can transition more affordably."
    },
    {
        "id": "news-us-stem-opt",
        "title": "United States: 36-Month STEM OPT Rules Maintained for Tech & Engineering Majors",
        "date": "2024-2026 Policy Notice",
        "category": "Work Rights",
        "country": "United States",
        "summary": "International students completing qualifying STEM degrees can work up to 3 years post-graduation without H-1B sponsorship, giving 3 chances in the annual H-1B lottery.",
        "impact": "Critical for maximum earning and ROI recovery."
    }
]


def get_live_opportunities(
    destination: Optional[str] = None,
    degree_level: Optional[str] = None,
    funding_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Filters curated active scholarships by destination, degree, and funding model.
    """
    results = ACTIVE_GLOBAL_SCHOLARSHIPS

    if destination and destination.strip():
        dest_low = destination.lower().strip()
        results = [s for s in results if dest_low in s["destination"].lower()]

    if degree_level and degree_level.strip():
        deg_up = degree_level.upper().strip()
        results = [s for s in results if any(deg_up == d.upper() for d in s.get("degree_levels", []))]

    if funding_type and funding_type.strip():
        fund_low = funding_type.lower().strip()
        results = [s for s in results if fund_low in s.get("funding_type", "").lower()]

    return results


def get_immigration_news() -> List[Dict[str, Any]]:
    """
    Returns latest regulatory policy updates for study destinations.
    """
    return IMMIGRATION_AND_STUDY_NEWS


def search_live_scholarship_opportunities(query: str) -> List[Dict[str, str]]:
    """
    Queries live web search via DuckDuckGo for real-time newly announced scholarship programs.
    """
    enhanced_query = f"{query} scholarship funding deadline application 2025 2026"
    return search_web_knowledge(enhanced_query, max_results=4)
