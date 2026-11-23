"""
tools/living_cost_tool.py - Currency Conversion, City Cost Index & Embassy Visa Checklists
Provides cost comparisons across student cities, exchange rate calculations, and visa paperwork rubrics.
"""

from typing import Dict, Any, List

# Approximate baseline currency exchange rates relative to USD
EXCHANGE_RATES = {
    "USD": 1.0,
    "EUR": 0.92,
    "GBP": 0.79,
    "CAD": 1.36,
    "AUD": 1.52,
    "INR": 83.5,
    "BDT": 117.5,
    "JPY": 155.0,
    "SEK": 10.6,
    "CHF": 0.90
}

# Average monthly student living expense index (in USD)
CITY_COST_INDEX = {
    "munich": {"city": "Munich, Germany", "monthly_rent": 650, "monthly_food": 250, "transport": 49, "total_monthly": 1050},
    "berlin": {"city": "Berlin, Germany", "monthly_rent": 580, "monthly_food": 240, "transport": 49, "total_monthly": 980},
    "aachen": {"city": "Aachen, Germany", "monthly_rent": 420, "monthly_food": 220, "transport": 0, "total_monthly": 750},
    "london": {"city": "London, UK", "monthly_rent": 1100, "monthly_food": 320, "transport": 130, "total_monthly": 1750},
    "manchester": {"city": "Manchester, UK", "monthly_rent": 700, "monthly_food": 260, "transport": 80, "total_monthly": 1180},
    "new york": {"city": "New York, USA", "monthly_rent": 1400, "monthly_food": 400, "transport": 130, "total_monthly": 2150},
    "san francisco": {"city": "San Francisco / Bay Area, USA", "monthly_rent": 1500, "monthly_food": 420, "transport": 120, "total_monthly": 2250},
    "austin": {"city": "Austin, USA", "monthly_rent": 850, "monthly_food": 300, "transport": 70, "total_monthly": 1350},
    "toronto": {"city": "Toronto, Canada", "monthly_rent": 950, "monthly_food": 320, "transport": 120, "total_monthly": 1520},
    "vancouver": {"city": "Vancouver, Canada", "monthly_rent": 1050, "monthly_food": 340, "transport": 110, "total_monthly": 1650},
    "sydney": {"city": "Sydney, Australia", "monthly_rent": 1000, "monthly_food": 350, "transport": 110, "total_monthly": 1600},
    "melbourne": {"city": "Melbourne, Australia", "monthly_rent": 900, "monthly_food": 330, "transport": 100, "total_monthly": 1460},
    "amsterdam": {"city": "Amsterdam, Netherlands", "monthly_rent": 850, "monthly_food": 300, "transport": 90, "total_monthly": 1380},
    "zurich": {"city": "Zurich, Switzerland", "monthly_rent": 1100, "monthly_food": 450, "transport": 80, "total_monthly": 1850}
}


def convert_currency(amount_usd: float, target_currency: str) -> Dict[str, Any]:
    """
    Converts USD amount to target global currency.
    """
    curr = target_currency.upper().strip()
    rate = EXCHANGE_RATES.get(curr, 1.0)
    converted = round(amount_usd * rate, 2)
    return {
        "amount_usd": amount_usd,
        "target_currency": curr,
        "exchange_rate": rate,
        "converted_amount": converted
    }


def get_city_living_cost(city_name: str) -> Dict[str, Any]:
    """
    Fetches student living expenses by city.
    """
    key = city_name.lower().strip()
    for k, v in CITY_COST_INDEX.items():
        if k in key or key in k:
            return v
    return {
        "city": city_name.title(),
        "monthly_rent": 750,
        "monthly_food": 280,
        "transport": 80,
        "total_monthly": 1200
    }


def get_embassy_visa_checklist(country: str) -> Dict[str, Any]:
    """
    Returns country-specific mandatory student visa documentation checklist.
    """
    c_low = country.lower().strip()

    if "germany" in c_low:
        return {
            "country": "Germany (National Visa / Type D)",
            "mandatory_documents": [
                "Unconditional admission letter (Zulassungsbescheid) from university",
                "Blocked Account (Sperrkonto) confirmation: ~€11,904 in Expatrio, Coracle, or Fintiba",
                "APS Certificate (Mandatory for India, China, Vietnam)",
                "Statutory Health Insurance (TK, Barmer, or DAK) or incoming travel coverage",
                "Valid passport with at least 12 months validity",
                "Motivational statement explaining study choice in Germany",
                "Certified copies of degree certificates & transcripts"
            ]
        }
    elif "canada" in c_low:
        return {
            "country": "Canada (Study Permit)",
            "mandatory_documents": [
                "Letter of Acceptance (LOA) with DLI number",
                "Provincial Attestation Letter (PAL) (unless exempt, e.g. Master's/PhD)",
                "Guaranteed Investment Certificate (GIC) of $20,635 CAD from approved Canadian bank",
                "Proof of 1st year paid tuition receipt",
                "Upfront medical examination by panel physician",
                "Police clearance certificate (PCC)",
                "Statement of Purpose addressing home ties"
            ]
        }
    elif "united states" in c_low or "usa" in c_low:
        return {
            "country": "United States (F-1 Student Visa)",
            "mandatory_documents": [
                "Form I-20 issued by university (SEVIS fee paid receipt: $350)",
                "DS-160 confirmation barcode",
                "Official bank statement showing liquid funds covering 1st year tuition + living ($40k-$80k)",
                "Official GRE / TOEFL / IELTS score reports",
                "Academic transcripts and degree diplomas",
                "Evidence of intent to return home upon degree completion"
            ]
        }
    elif "united kingdom" in c_low or "uk" in c_low:
        return {
            "country": "United Kingdom (Student Visa)",
            "mandatory_documents": [
                "Confirmation of Acceptance for Studies (CAS) from sponsor university",
                "Maintenance funds held for 28 consecutive days (£12,006 London / £9,207 outside)",
                "Immigration Health Surcharge (IHS) payment (£776/year)",
                "ATAS certificate for sensitive STEM fields",
                "TB test certificate from approved clinic",
                "English language proficiency certificate"
            ]
        }
    else:
        return {
            "country": country.title(),
            "mandatory_documents": [
                "Official university acceptance letter",
                "Proof of sufficient financial means covering tuition and subsistence",
                "Comprehensive international student health insurance",
                "Valid passport and biometric photographs",
                "Academic transcripts and diploma",
                "Clean police certificate and medical clearance"
            ]
        }
