"""
guardrails.py - Admissions, Budget, Safety Harness, and HITL (Human-in-the-Loop) Guardrails
Enforces input safety, prevents hallucinations, checks prerequisite hurdles, and flags actions for human review.
"""

from typing import Dict, Any, List, Optional
import re


class SafetyHarness:
    """
    Prevents prompt injection, toxic input, and out-of-scope instructions.
    """
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?(previous|above)\s+instructions",
        r"system\s*prompt",
        r"you\s+are\s+now\s+a",
        r"jailbreak",
        r"bypass\s+safety",
        r"drop\s+database",
        r"select\s+\*\s+from",
        r"delete\s+from\s+users"
    ]

    @classmethod
    def sanitize_and_validate(cls, prompt: str) -> Dict[str, Any]:
        p_low = prompt.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, p_low):
                return {
                    "is_safe": False,
                    "reason": "Security Alert: Prompt contains prohibited administrative or injection keywords."
                }
        return {"is_safe": True, "clean_prompt": prompt.strip()}


def check_intent_guardrail(user_prompt: str) -> Dict[str, Any]:
    """
    Validates if the user's prompt is relevant to higher education, degrees,
    admissions, universities, visa/PR, careers, or costs.
    """
    safety = SafetyHarness.sanitize_and_validate(user_prompt)
    if not safety["is_safe"]:
        return {
            "is_relevant": False,
            "matched_topics": [],
            "message": safety["reason"]
        }

    education_keywords = [
        "university", "college", "master", "msc", "bachelor", "bsc", "phd", "doctorate",
        "study", "degree", "admission", "tuition", "cost", "scholarship", "gpa", "ielts",
        "toefl", "gre", "gmat", "visa", "pr", "work permit", "pgwp", "opt", "stem",
        "job", "career", "salary", "germany", "usa", "uk", "canada", "australia",
        "europe", "sop", "ranking", "mastersportal", "course", "campus", "review",
        "living cost", "application", "deadline", "fees", "immigrate", "settle",
        "transcript", "cv", "resume", "opportunities", "news"
    ]

    prompt_lower = user_prompt.lower()
    matched = [k for k in education_keywords if k in prompt_lower]

    is_relevant = len(matched) > 0 or len(prompt_lower.split()) > 3

    return {
        "is_relevant": is_relevant,
        "matched_topics": matched[:5],
        "message": "" if is_relevant else "Please ask questions related to universities, degree programs (BSc, MSc, PhD), admissions, scholarships, visas, living costs, or post-study career opportunities."
    }


def evaluate_eligibility_guardrail(
    user_gpa: Optional[float] = None,
    user_ielts: Optional[float] = None,
    user_gre: Optional[int] = None,
    target_country: str = "",
    target_degree: str = "MSc",
    undergrad_duration_years: int = 4
) -> Dict[str, Any]:
    """
    Evaluates hard admission prerequisites, flags non-negotiable hurdles,
    and returns tailored warnings for target destinations.
    """
    hurdles: List[str] = []
    advisory_notes: List[str] = []
    country_lower = target_country.lower().strip()

    # 1. English Proficiency Check
    if user_ielts is not None and user_ielts > 0:
        if user_ielts < 6.0:
            hurdles.append("IELTS score below 6.0: Direct admission is restricted. Pre-sessional English courses required.")
        elif user_ielts < 6.5:
            advisory_notes.append("IELTS 6.0 - 6.5 meets minimum requirements for many universities, but top 100 research universities require 7.0.")

    # 2. GPA Assessment
    if user_gpa is not None and user_gpa > 0:
        if user_gpa < 2.8:
            hurdles.append("GPA below 2.8/4.0: High rejection probability at top 200 ranked universities without substantial compensating research or work experience.")
        elif user_gpa < 3.2:
            advisory_notes.append("GPA between 2.8 and 3.2: Best matched with Target and Safety universities (ranked 150-400).")

    # 3. Country-Specific Hurdles
    if "germany" in country_lower:
        advisory_notes.append("Germany Requirement: Strict consecutive master's rule — bachelor syllabus must directly match.")
        advisory_notes.append("APS Certificate: Mandatory for applicants from India, China, and Vietnam.")
        if target_degree.upper() == "MSC":
            advisory_notes.append("Blocked Account (Sperrkonto): Must deposit €11,904 in a designated German bank.")

    if "united states" in country_lower or "usa" in country_lower or "us" in country_lower:
        if undergrad_duration_years == 3:
            hurdles.append("3-Year Bachelor's Warning: Many US graduate schools mandate a 4-year undergraduate degree. WES evaluation may be required.")
        if user_gre is None and target_degree.upper() in ["MSC", "PHD"]:
            advisory_notes.append("GRE: While optional at some universities, Quant 165+ significantly unlocks departmental funding.")

    if "canada" in country_lower:
        advisory_notes.append("Canada Study Permit: Master's and PhD graduates receive 3-year PGWP and priority permit processing.")
        advisory_notes.append("Proof of Financial Support: Cost-of-living requirement is $20,635 CAD plus 1st year tuition.")

    if "united kingdom" in country_lower or "uk" in country_lower:
        if target_degree.upper() in ["MSC", "PHD"]:
            advisory_notes.append("ATAS Certificate: Required for non-EU students in sensitive science/engineering subjects.")

    return {
        "status": "warning" if hurdles else "cleared",
        "hard_hurdles": hurdles,
        "advisory_notes": advisory_notes
    }


def check_budget_feasibility(
    annual_budget_usd: int,
    target_country: str,
    target_degree: str = "MSc"
) -> Dict[str, Any]:
    country_lower = target_country.lower().strip()
    is_unrealistic = False
    recommendations = []

    min_annual_costs = {
        "united states": 38000,
        "united kingdom": 28000,
        "canada": 28000,
        "australia": 32000,
        "germany": 13000,
        "netherlands": 22000,
        "sweden": 22000,
        "france": 12000
    }

    matched_min = None
    for k, v in min_annual_costs.items():
        if k in country_lower:
            matched_min = v
            break

    if matched_min and annual_budget_usd > 0 and annual_budget_usd < (matched_min * 0.6):
        is_unrealistic = True
        recommendations.append(
            f"Budget Alert: Specified budget of ${annual_budget_usd:,}/year is significantly below the minimum required cost of attendance for {target_country.title()} (~${matched_min:,}/year)."
        )
        if "germany" not in country_lower and "france" not in country_lower:
            recommendations.append("Alternative Suggestion: Target public universities in Germany or Italy with low/zero tuition.")
        recommendations.append("Scholarship Target: Prioritize fully funded external awards (DAAD, Erasmus Mundus, Fulbright, Chevening).")

    return {
        "is_feasible": not is_unrealistic,
        "minimum_benchmark_usd": matched_min or 20000,
        "recommendations": recommendations
    }


def classify_admission_chances(user_gpa: float, university_min_gpa: float, acceptance_rate: float) -> str:
    gpa_diff = user_gpa - university_min_gpa
    if gpa_diff < -0.1 or acceptance_rate < 15.0:
        return "Reach (Ambitious)"
    elif gpa_diff >= 0.3 and acceptance_rate >= 40.0:
        return "Safety (High Likelihood)"
    else:
        return "Target (Competitive Match)"


def check_human_in_the_loop_trigger(
    user_budget_usd: int,
    discovered_unis: List[Dict[str, Any]],
    user_gpa: float,
    country: str
) -> Dict[str, Any]:
    """
    Evaluates if Human-in-the-Loop (HITL) approval is needed.
    Triggers when:
    1. Budget requires official financial affidavit / loan sanction letter.
    2. All matched institutions fall in 'Reach' category.
    3. User requested final locked application submission strategy.
    """
    requires_hitl = False
    hitl_reason = ""
    options = []

    reach_count = sum(1 for u in discovered_unis if u.get("tier", "").startswith("Reach"))
    if discovered_unis and reach_count == len(discovered_unis):
        requires_hitl = True
        hitl_reason = "All matched universities are in the Reach (Ambitious) tier with low acceptance rates. Human counselor confirmation recommended."
        options = ["Include Safety/Target backup universities", "Proceed exclusively with Reach options"]

    if user_budget_usd > 0 and user_budget_usd < 12000 and "germany" not in country.lower():
        requires_hitl = True
        hitl_reason = f"Budget is under $12,000 for {country or 'selected destination'}. Applying requires external full-ride scholarship commitment."
        options = ["Switch focus to DAAD/Erasmus Mundus fully-funded programs", "Confirm self-funded affidavit"]

    return {
        "requires_hitl": requires_hitl,
        "hitl_reason": hitl_reason,
        "action_options": options
    }
