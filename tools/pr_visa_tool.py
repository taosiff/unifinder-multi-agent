"""
tools/pr_visa_tool.py - Immigration, Post-Study Work Visa (PSWV) & PR Pathway Engine
Evaluates post-study work permit duration, permanent residency requirements,
and point-based immigration systems across destination countries.
"""

from typing import Dict, Any

COUNTRY_IMMIGRATION_RULES = {
    "germany": {
        "pswv_duration": "18 months (Jobseeker Visa / Aufenthaltserlaubnis zur Arbeitsplatzsuche)",
        "work_during_study": "140 full days or 280 half days per calendar year (recently increased from 120/240)",
        "pr_pathway": "EU Blue Card (Blaue Karte EU) -> Fast-track PR (Niederlassungserlaubnis)",
        "pr_timeline": "21 months with B1 German language certificate, or 27 months with basic German (A1/A2)",
        "salary_threshold": "Reduced salary threshold for STEM/shortage occupations: ~€41,041/year (2024-2026 rules)",
        "pr_difficulty": "Low to Moderate (One of the most welcoming for STEM graduates in Europe)",
        "key_advantages": "No tuition or minimal tuition at public universities, free EU travel, spouse can work without restriction.",
        "financial_proof": "Blocked Account (Sperrkonto) required: ~€11,904 per year."
    },
    "canada": {
        "pswv_duration": "Up to 3 years (Post-Graduation Work Permit - PGWP for eligible 2-year programs or master's degrees)",
        "work_during_study": "Up to 24 hours per week off-campus during academic sessions",
        "pr_pathway": "Express Entry (Canadian Experience Class - CEC, Federal Skilled Worker), Provincial Nominee Programs (PNP)",
        "pr_timeline": "Typically 1-2 years of qualified Canadian work experience (TEER 0, 1, 2, 3) to achieve competitive CRS score",
        "salary_threshold": "Prevailing wage for NOC category",
        "pr_difficulty": "Moderate to High (Recent caps on international study permits and higher CRS cut-offs; master's graduates receive 3-year PGWP regardless of program length)",
        "key_advantages": "Category-based selection for STEM, Healthcare, and Francophone speakers; clear family sponsorship.",
        "financial_proof": "Guaranteed Investment Certificate (GIC) or proof of funds: $20,635 CAD plus 1st year tuition."
    },
    "united kingdom": {
        "pswv_duration": "2 years (Graduate Route Visa for BSc/MSc), 3 years for PhD graduates",
        "work_during_study": "20 hours per week during term time",
        "pr_pathway": "Switch to Skilled Worker Visa (sponsored employer) -> Indefinite Leave to Remain (ILR) after 5 years",
        "pr_timeline": "5 years continuous employment on Skilled Worker Visa",
        "salary_threshold": "New standard threshold £38,700/year (new entrant discounts apply to recent graduates under 26 or switching from student visa: ~£30,960)",
        "pr_difficulty": "Moderate (Sponsorship required; stringent salary threshold unless in shortage fields)",
        "key_advantages": "World-leading academic brand, 1-year master's degree saves living and opportunity costs.",
        "financial_proof": "£1,334/month for London (up to 9 months = £12,006) or £1,023/month outside London."
    },
    "united states": {
        "pswv_duration": "12 months standard OPT + 24 months STEM OPT Extension (Total: 36 months for STEM majors)",
        "work_during_study": "20 hours/week on-campus only (CPT allowed for qualifying internships)",
        "pr_pathway": "OPT -> H-1B Specialty Occupation Visa (annual lottery with 20,000 master's cap) -> Employment-based Green Card (EB-2 / EB-3) or EB-2 NIW (National Interest Waiver for PhD/researchers)",
        "pr_timeline": "Varies significantly by country of birth (India/China backlogged; rest of world: 2-4 years)",
        "salary_threshold": "Prevailing wage determination by Department of Labor",
        "pr_difficulty": "High (H-1B lottery dependency, though STEM OPT provides 3 lottery attempts)",
        "key_advantages": "Highest post-graduation tech and finance salaries in the world ($100k - $160k+), unmatched innovation hub.",
        "financial_proof": "Form I-20 proof of liquid funds covering full 1st year tuition + living costs ($45k - $85k USD)."
    },
    "australia": {
        "pswv_duration": "2 to 4 years (Temporary Graduate Visa Subclass 485 - varies by degree and regional location)",
        "work_during_study": "48 hours per fortnight",
        "pr_pathway": "General Skilled Migration: Subclass 189 (Skilled Independent), 190 (State Nominated), 491 (Regional)",
        "pr_timeline": "Points test (minimum 65 points, competitive score typically 85+ points with skills assessment)",
        "salary_threshold": "TSMIT minimum salary threshold: $70,000 AUD",
        "pr_difficulty": "Moderate to High (Points competitive, but studying in regional areas gives 5 extra points and longer work rights)",
        "key_advantages": "Exceptional work-life balance, high minimum wages ($23.23 AUD/hr), strong demand in engineering, healthcare, IT.",
        "financial_proof": "Proof of living costs: $24,505 AUD per year plus 1st year tuition."
    },
    "netherlands": {
        "pswv_duration": "1 year (Orientation Year / Zoekjaar visa for highly educated graduates)",
        "work_during_study": "16 hours per week (work permit required)",
        "pr_pathway": "Zoekjaar -> Highly Skilled Migrant (Kennismigrant) permit -> Permanent Residence / Dutch EU Citizen after 5 years",
        "pr_timeline": "5 years continuous lawful residence with A2/B1 civic integration",
        "salary_threshold": "Reduced salary threshold for Orientation Year graduates: ~€2,801 gross per month",
        "pr_difficulty": "Low to Moderate (Favorable reduced salary requirement for alumni of Dutch universities)",
        "key_advantages": "Virtually 100% English fluency in society, major European tech headquarters (ASML, Booking.com, Uber).",
        "financial_proof": "Proof of living expenses: ~€1,200 per month (€14,400/year)."
    },
    "sweden": {
        "pswv_duration": "12 months job-seeking residence permit after graduation",
        "work_during_study": "No statutory hourly limit, provided student makes progress in studies",
        "pr_pathway": "Work permit for 4 years -> Permanent Residence (Permanent Uppehållstillstånd)",
        "pr_timeline": "4 years of working under a Swedish work permit within a 7-year period",
        "salary_threshold": "Collective agreement wage (minimum 80% of median salary ~28,480 SEK/mo)",
        "pr_difficulty": "Moderate (Requires maintaining qualifying employment for 4 years)",
        "key_advantages": "Generous social system, world-leading innovation and sustainability culture, high English proficiency.",
        "financial_proof": "Proof of funds: 10,314 SEK per month."
    }
}


def evaluate_immigration_pathway(
    country: str,
    degree_level: str = "MSc",
    major: str = "Computer Science",
    user_age: int = 25
) -> Dict[str, Any]:
    """
    Evaluates the Post-Study Work Visa rights, PR feasibility, points, and financial requirements.
    """
    country_key = country.lower().strip()
    rule = None
    for k, v in COUNTRY_IMMIGRATION_RULES.items():
        if k in country_key or country_key in k:
            rule = v
            country_matched = k.title()
            break

    if not rule:
        # Default global EU/standard overview
        return {
            "country": country,
            "pswv_duration": "Typically 1 to 2 years post-graduation work rights depending on degree level",
            "work_during_study": "Typically 20 hours/week during semesters",
            "pr_pathway": "Transition to national work permit / Skilled migrant scheme",
            "pr_difficulty": "Moderate",
            "financial_proof": "Standard proof of living funds (~$12,000 - $18,000 USD/year) required for student visa.",
            "recommendation": f"Verify direct embassy criteria for {country} regarding recent work rights."
        }

    # Custom STEM & Degree benefits
    is_stem = any(term in major.lower() for term in ["computer", "data", "ai", "engineer", "math", "tech", "biology", "physics", "robotics"])
    stem_bonus = ""
    if is_stem:
        if country_matched == "United States":
            stem_bonus = "STEM Major Bonus: Eligible for 24-month STEM OPT Extension (total 36 months of US work authorization without H-1B)."
        elif country_matched == "Germany":
            stem_bonus = "STEM Major Bonus: Eligible for EU Blue Card with lowered salary threshold (~€41,041)."
        elif country_matched == "Canada":
            stem_bonus = "STEM Major Bonus: Eligible for targeted Express Entry STEM category-based draws with lower CRS cutoffs."

    return {
        "country": country_matched,
        "degree_level": degree_level,
        "is_stem": is_stem,
        "stem_benefit": stem_bonus,
        "pswv_duration": rule["pswv_duration"],
        "work_during_study": rule["work_during_study"],
        "pr_pathway": rule["pr_pathway"],
        "pr_timeline": rule["pr_timeline"],
        "salary_threshold": rule["salary_threshold"],
        "pr_difficulty": rule["pr_difficulty"],
        "key_advantages": rule["key_advantages"],
        "financial_proof": rule["financial_proof"]
    }
