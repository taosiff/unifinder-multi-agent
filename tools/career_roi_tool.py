"""
tools/career_roi_tool.py - Career Outlook, Salary Benchmarking & Financial ROI Engine
Calculates tuition payback period, post-study salary projections, and industry demand metrics.
"""

from typing import Dict, Any

# Benchmarks for typical starting salaries by country and discipline (USD equivalent)
BENCHMARK_SALARIES = {
    "united states": {
        "computer science": {"avg_start_usd": 115000, "high_start_usd": 165000, "demand": "Very High"},
        "data science": {"avg_start_usd": 110000, "high_start_usd": 155000, "demand": "Very High"},
        "engineering": {"avg_start_usd": 88000, "high_start_usd": 125000, "demand": "High"},
        "business": {"avg_start_usd": 85000, "high_start_usd": 135000, "demand": "High"},
        "finance": {"avg_start_usd": 95000, "high_start_usd": 150000, "demand": "Very High"},
        "humanities": {"avg_start_usd": 55000, "high_start_usd": 75000, "demand": "Moderate"},
        "default": {"avg_start_usd": 75000, "high_start_usd": 105000, "demand": "Moderate"}
    },
    "germany": {
        "computer science": {"avg_start_usd": 68000, "high_start_usd": 90000, "demand": "Very High (Shortage)"},
        "data science": {"avg_start_usd": 66000, "high_start_usd": 88000, "demand": "Very High"},
        "engineering": {"avg_start_usd": 65000, "high_start_usd": 85000, "demand": "Very High"},
        "business": {"avg_start_usd": 55000, "high_start_usd": 78000, "demand": "High"},
        "finance": {"avg_start_usd": 62000, "high_start_usd": 85000, "demand": "High"},
        "humanities": {"avg_start_usd": 42000, "high_start_usd": 55000, "demand": "Moderate"},
        "default": {"avg_start_usd": 52000, "high_start_usd": 70000, "demand": "High"}
    },
    "united kingdom": {
        "computer science": {"avg_start_usd": 58000, "high_start_usd": 85000, "demand": "High"},
        "data science": {"avg_start_usd": 56000, "high_start_usd": 82000, "demand": "High"},
        "engineering": {"avg_start_usd": 48000, "high_start_usd": 70000, "demand": "High"},
        "business": {"avg_start_usd": 46000, "high_start_usd": 75000, "demand": "High"},
        "finance": {"avg_start_usd": 65000, "high_start_usd": 105000, "demand": "Very High"},
        "humanities": {"avg_start_usd": 35000, "high_start_usd": 48000, "demand": "Moderate"},
        "default": {"avg_start_usd": 45000, "high_start_usd": 65000, "demand": "Moderate"}
    },
    "canada": {
        "computer science": {"avg_start_usd": 72000, "high_start_usd": 98000, "demand": "High"},
        "data science": {"avg_start_usd": 70000, "high_start_usd": 95000, "demand": "High"},
        "engineering": {"avg_start_usd": 62000, "high_start_usd": 85000, "demand": "High"},
        "business": {"avg_start_usd": 54000, "high_start_usd": 78000, "demand": "Moderate"},
        "finance": {"avg_start_usd": 60000, "high_start_usd": 88000, "demand": "High"},
        "humanities": {"avg_start_usd": 40000, "high_start_usd": 52000, "demand": "Moderate"},
        "default": {"avg_start_usd": 52000, "high_start_usd": 70000, "demand": "Moderate"}
    },
    "australia": {
        "computer science": {"avg_start_usd": 70000, "high_start_usd": 95000, "demand": "High"},
        "data science": {"avg_start_usd": 68000, "high_start_usd": 92000, "demand": "High"},
        "engineering": {"avg_start_usd": 65000, "high_start_usd": 88000, "demand": "Very High"},
        "business": {"avg_start_usd": 52000, "high_start_usd": 75000, "demand": "Moderate"},
        "finance": {"avg_start_usd": 62000, "high_start_usd": 90000, "demand": "High"},
        "humanities": {"avg_start_usd": 42000, "high_start_usd": 55000, "demand": "Moderate"},
        "default": {"avg_start_usd": 54000, "high_start_usd": 72000, "demand": "Moderate"}
    },
    "netherlands": {
        "computer science": {"avg_start_usd": 62000, "high_start_usd": 85000, "demand": "Very High"},
        "data science": {"avg_start_usd": 60000, "high_start_usd": 82000, "demand": "Very High"},
        "engineering": {"avg_start_usd": 58000, "high_start_usd": 78000, "demand": "Very High"},
        "business": {"avg_start_usd": 50000, "high_start_usd": 72000, "demand": "High"},
        "finance": {"avg_start_usd": 56000, "high_start_usd": 80000, "demand": "High"},
        "default": {"avg_start_usd": 50000, "high_start_usd": 68000, "demand": "High"}
    }
}


def calculate_roi_and_career_outlook(
    country: str,
    subject: str,
    degree_level: str = "MSc",
    annual_tuition_usd: int = 15000,
    annual_living_cost_usd: int = 14000,
    program_duration_years: float = 2.0,
    scholarship_amount_usd: int = 0
) -> Dict[str, Any]:
    """
    Computes precise Total Cost of Attendance (COA), projected starting salary,
    tax-adjusted savings rate, and estimated payback period in years.
    """
    c_key = country.lower().strip()
    country_data = None
    for k, v in BENCHMARK_SALARIES.items():
        if k in c_key or c_key in k:
            country_data = v
            break

    if not country_data:
        country_data = BENCHMARK_SALARIES["germany"]

    subj_key = "default"
    for s_name in ["computer science", "data science", "engineering", "business", "finance", "humanities"]:
        if s_name in subject.lower():
            subj_key = s_name
            break

    salary_info = country_data.get(subj_key, country_data.get("default"))

    # Financial breakdown
    total_tuition = max(0, int(annual_tuition_usd * program_duration_years) - scholarship_amount_usd)
    total_living = int(annual_living_cost_usd * program_duration_years)

    # Estimate part-time earnings (e.g. 20 hrs/week * $14/hr avg * 36 weeks/yr = ~$10,000/yr)
    estimated_part_time_earnings = int(10000 * program_duration_years)
    net_total_investment = max(0, (total_tuition + total_living) - estimated_part_time_earnings)

    avg_annual_salary = salary_info["avg_start_usd"]
    # Approximate post-tax and living annual savings capacity (~30% of gross salary)
    annual_savings_capacity = int(avg_annual_salary * 0.32)

    if annual_savings_capacity > 0:
        payback_years = round(net_total_investment / annual_savings_capacity, 1)
    else:
        payback_years = 1.0

    # 3-year and 5-year cumulative financial return
    three_year_net = (annual_savings_capacity * 3) - net_total_investment
    five_year_net = (annual_savings_capacity * 5) - net_total_investment

    roi_rating = "Exceptional" if payback_years <= 1.5 else "Strong" if payback_years <= 3.0 else "Moderate"

    return {
        "discipline": subject,
        "country": country.title(),
        "program_duration_years": program_duration_years,
        "total_tuition_usd": total_tuition,
        "total_living_usd": total_living,
        "estimated_part_time_earnings_usd": estimated_part_time_earnings,
        "net_total_investment_usd": net_total_investment,
        "projected_starting_salary_avg_usd": avg_annual_salary,
        "projected_starting_salary_high_usd": salary_info["high_start_usd"],
        "industry_demand": salary_info["demand"],
        "estimated_annual_savings_usd": annual_savings_capacity,
        "payback_period_years": payback_years,
        "three_year_net_profit_usd": three_year_net,
        "five_year_net_profit_usd": five_year_net,
        "roi_rating": roi_rating
    }
