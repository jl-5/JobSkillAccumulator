from collections import Counter

from app.models import IndustryCount, JobPosting

OTHER = "Other"

# Fixed taxonomy so the pie chart stays consistent across searches instead of
# accumulating one-off freeform labels.
INDUSTRIES: list[str] = [
    "Technology",
    "Healthcare",
    "Finance",
    "Retail & E-commerce",
    "Education",
    "Nonprofit & Government",
    "Media & Entertainment",
    "Manufacturing & Engineering",
    "Real Estate",
    "Hospitality & Travel",
    "Legal",
    "Transportation & Logistics",
    "Energy",
    "Construction & Trade",
    "Sales & Marketing",
    "Science & Research",
    "Consulting & Professional Services",
]

# Keyword-based classifier (no source currently provides a structured
# industry/category field). Approximate by design, same spirit as
# keyword_extraction.py's skill matcher: scores each industry by how many of
# its signal phrases appear in the company name + posting text, picks the
# highest. Falls back to "Other" if nothing matches.
_INDUSTRY_KEYWORDS: dict[str, list[str]] = {
    "Technology": [
        "software company", "saas", "tech startup", "technology company",
        "cloud computing", "artificial intelligence", "machine learning",
        "developer platform", "mobile app", "web application", "fintech",
        "open source", "api platform",
    ],
    "Healthcare": [
        "hospital", "clinic", "healthcare", "health system", "medical center",
        "patient care", "pharmaceutical", "biotech", "biotechnology",
        "life sciences", "medical device", "telehealth", "health insurance",
    ],
    "Finance": [
        "bank", "banking", "investment firm", "hedge fund", "asset management",
        "insurance company", "financial services", "wealth management",
        "venture capital", "private equity", "accounting firm", "credit union",
    ],
    "Retail & E-commerce": [
        "retailer", "retail store", "e-commerce", "ecommerce", "online store",
        "consumer goods", "apparel brand", "fashion brand", "grocery",
        "supermarket",
    ],
    "Education": [
        "university", "college", "school district", "k-12", "higher education",
        "elementary school", "high school", "education company", "edtech",
    ],
    "Nonprofit & Government": [
        "nonprofit", "non-profit", "charity", "ngo", "government agency",
        "federal agency", "state government", "public sector", "foundation",
    ],
    "Media & Entertainment": [
        "media company", "entertainment company", "film studio",
        "television network", "streaming service", "publishing house",
        "news organization", "gaming studio", "video game", "creative agency",
        "record label",
    ],
    "Manufacturing & Engineering": [
        "manufacturer", "manufacturing facility", "factory",
        "industrial equipment", "automotive manufacturer", "aerospace",
        "production facility", "engineering firm",
    ],
    "Real Estate": [
        "real estate", "property management", "commercial real estate",
        "residential real estate", "realty", "brokerage firm",
    ],
    "Hospitality & Travel": [
        "hotel", "resort", "restaurant", "hospitality group", "airline",
        "cruise line", "travel agency", "tourism",
    ],
    "Legal": [
        "law firm", "legal services", "attorneys at law", "legal department",
    ],
    "Transportation & Logistics": [
        "logistics company", "shipping company", "freight", "warehouse",
        "supply chain", "trucking company", "delivery service",
    ],
    "Energy": [
        "energy company", "oil and gas", "renewable energy", "solar energy",
        "utility company", "power plant",
    ],
    "Construction & Trade": [
        "construction company", "general contractor", "building contractor",
        "construction firm",
    ],
    "Sales & Marketing": [
        "marketing agency", "digital marketing", "marketing firm",
        "advertising agency",
    ],
    "Science & Research": [
        "research institute", "research laboratory", "scientific research",
        "laboratory services",
    ],
    "Consulting & Professional Services": [
        "consulting firm", "management consulting", "professional services firm",
        "staffing agency", "recruiting firm", "hr services",
    ],
}

_SCAN_CHARS = 1500


def classify_industry(posting: JobPosting) -> str:
    haystack = f"{posting.company or ''} {posting.title} {posting.description[:_SCAN_CHARS]}".lower()

    best_industry = OTHER
    best_score = 0
    for industry, keywords in _INDUSTRY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in haystack)
        if score > best_score:
            best_score = score
            best_industry = industry
    return best_industry


def aggregate_industries(postings: list[JobPosting]) -> list[IndustryCount]:
    total = len(postings)
    if total == 0:
        return []

    counts = Counter(classify_industry(posting) for posting in postings)
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [
        IndustryCount(industry=industry, count=count, percentage=round(count / total * 100, 1))
        for industry, count in ranked
    ]
