"""
tools/sop_reviewer_tool.py - Statement of Purpose (SOP) & Academic Profile Reviewer
Critiques user drafts against international university admissions rubrics.
"""

from typing import Dict, Any
import re

def review_statement_of_purpose(sop_text: str, target_program: str = "", target_university: str = "") -> Dict[str, Any]:
    """
    Evaluates SOP word count, hook originality, research specificity, and tone.
    """
    words = sop_text.strip().split()
    word_count = len(words)

    strengths = []
    critiques = []
    suggestions = []

    # Word count check
    if word_count < 300:
        critiques.append("Too brief. Standard graduate SOPs range between 600 - 1,000 words.")
    elif word_count > 1200:
        critiques.append(f"Lengthy ({word_count} words). Admissions committees prefer concise essays under 1,000 words.")
    else:
        strengths.append(f"Optimal length ({word_count} words).")

    # Cliché detection
    cliches = [
        "since my childhood", "ever since i was a child", "i have always been fascinated",
        "passion for learning", "dream university", "reputed institution"
    ]
    found_cliches = [c for c in cliches if c in sop_text.lower()]
    if found_cliches:
        critiques.append(f"Contains cliché phrases: {', '.join([f'\"{c}\"' for c in found_cliches])}. Replace with specific project/research instances.")
    else:
        strengths.append("Avoids overused childhood origin clichés.")

    # Specificity check
    specific_signals = ["research", "thesis", "professor", "lab", "framework", "methodology", "algorithm", "case study", "publication"]
    signal_count = sum(1 for s in specific_signals if s in sop_text.lower())
    if signal_count >= 3:
        strengths.append("Demonstrates technical grounding and research awareness.")
    else:
        critiques.append("Lacks technical depth. Mention specific faculty members, laboratories, or elective modules you intend to pursue.")

    # Target university mention
    if target_university and target_university.lower() not in sop_text.lower():
        critiques.append(f"Does not explicitly reference '{target_university}'. Tailor paragraphs to explain why this specific department is essential.")
    elif target_university:
        strengths.append(f"Explicitly addresses fit with {target_university}.")

    score = 70
    score += len(strengths) * 7
    score -= len(critiques) * 8
    score = max(40, min(95, score))

    suggestions.append("Structure recommendation: 1. Academic Hook & Driving Question (15%), 2. Relevant Technical & Research Accomplishments (45%), 3. Why This Program & Specific Labs (25%), 4. 5-Year Career Vision (15%).")

    return {
        "word_count": word_count,
        "admissions_impact_score": score,
        "strengths": strengths,
        "critiques": critiques,
        "actionable_suggestions": suggestions
    }
