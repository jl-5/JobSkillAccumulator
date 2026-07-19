import re

# Companies whose primary business is defense/military contracting -
# checked against the inferred company name and the posting text, since
# many of these post under generic-sounding req titles that never mention
# "defense" anywhere in the body.
_DEFENSE_COMPANIES = [
    "lockheed martin",
    "raytheon",
    "rtx corporation",
    "northrop grumman",
    "general dynamics",
    "boeing defense",
    "l3harris",
    "l3 technologies",
    "bae systems",
    "leidos",
    "saic",
    "booz allen hamilton",
    "caci",
    "anduril",
    "textron",
    "huntington ingalls",
    "kratos defense",
    "amentum",
    "parsons corporation",
    "mantech",
    "peraton",
    "ball aerospace",
    "sierra nevada corporation",
]

# Phrases marking a posting as tied to defense/military/intelligence work
# or requiring a government security clearance - checked against the full
# posting text since these rarely appear in the title alone. Includes
# "department of war" alongside "department of defense"/"dod": the 2025
# executive order restored "Department of War" as an official secondary
# title for DoD, so postings referencing the department now use either
# name interchangeably.
_DEFENSE_SIGNALS = [
    "department of defense",
    "department of war",
    "department of the navy",
    "department of the army",
    "department of the air force",
    "united states air force",
    "u.s. air force",
    "united states army",
    "u.s. army",
    "united states navy",
    "u.s. navy",
    "united states marine corps",
    "u.s. marine corps",
    "space force",
    "defense contractor",
    "military contractor",
    "warfighter",
    "war fighter",
    "national security agency",
    "central intelligence agency",
    "defense advanced research projects agency",
    "darpa",
    "security clearance",
    "secret clearance",
    "top secret",
    "ts/sci",
    "public trust clearance",
    "polygraph",
    "itar",
    "dod",
    "nsa",
    "cia",
]


def _build_pattern(keywords: list[str]) -> re.Pattern:
    escaped = [re.escape(k) for k in keywords]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


_PATTERN = _build_pattern(_DEFENSE_COMPANIES + _DEFENSE_SIGNALS)

# US federal contractors are required (VEVRAA, 41 CFR 60-300.2) to include a
# standard "protected veteran" disclosure in their EEO statement, which
# defines "active duty wartime or campaign badge veteran" as one whose
# "campaign badge has been authorized under the laws administered by the
# Department of Defense" - this exact clause appears verbatim in nearly
# every US company's boilerplate regardless of industry (confirmed
# empirically on an Anthropic posting, which is not remotely
# defense-related), so it must be stripped before matching or it would
# false-positive on almost any US posting with an EEO statement.
_EEO_BOILERPLATE_RE = re.compile(
    r"laws administered by the (?:u\.s\.\s+)?department of (?:defense|war)",
    re.IGNORECASE,
)


def is_defense_related(text: str, company: str | None = None) -> bool:
    """True if the posting is tied to defense/military contracting or
    requires a government security clearance - either the company itself
    is a known defense contractor, or the posting text names a defense
    agency/branch or a clearance requirement."""
    combined = f"{company or ''} {text}"
    combined = _EEO_BOILERPLATE_RE.sub("", combined)
    return bool(_PATTERN.search(combined))
