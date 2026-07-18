import re

# The countries exposed in the UI dropdown as selectable search targets.
COUNTRIES: dict[str, str] = {
    "us": "United States",
    "gb": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "de": "Germany",
    "fr": "France",
    "in": "India",
    "nl": "Netherlands",
}

DEFAULT_COUNTRY = "us"

# Signals used to recognize a posting's country from free text (Google/
# Brave postings have no structured location field). This is
# deliberately much broader than `COUNTRIES` above: a posting based in, say,
# Poland or Singapore still needs to be recognized and excluded when the
# target is "us", even though the user can't pick Poland as a search target.
# Without this, "ambiguous -> include" (see matches_country) silently
# included postings from anywhere we didn't have a name for. Each entry
# includes the country name plus major cities, since many postings state a
# city without ever naming the country (e.g. "Located in downtown Toronto"
# with no mention of "Canada" anywhere on the page).
_COUNTRY_SIGNALS: dict[str, list[str]] = {
    "us": ["united states", "usa", "u.s.a", "u.s."],
    "gb": [
        "united kingdom", "great britain", "england", "scotland", "wales",
        "uk", "london", "manchester", "birmingham", "edinburgh", "glasgow",
        "bristol", "leeds",
    ],
    "ca": [
        "canada", "toronto", "vancouver", "montreal", "montréal", "ottawa",
        "calgary", "quebec", "québec", "edmonton", "winnipeg",
    ],
    "au": ["australia", "sydney", "melbourne", "brisbane", "perth", "adelaide"],
    "de": [
        "germany", "deutschland", "berlin", "munich", "münchen", "hamburg",
        "frankfurt", "cologne", "köln", "gmbh",
    ],
    "fr": ["france", "paris", "lyon", "marseille", "toulouse"],
    "in": [
        "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
        "pune", "chennai", "gurgaon", "gurugram", "noida",
    ],
    "nl": ["netherlands", "holland", "amsterdam", "rotterdam", "utrecht", "the hague"],
    # Common ATS-posting countries that aren't selectable UI targets, but
    # still need to be recognized so they're excluded rather than defaulting
    # to "ambiguous -> include" when the user picks a different target.
    "se": ["sweden", "stockholm", "malmö", "malmo", "gothenburg"],
    "pl": ["poland", "warsaw", "warszawa", "krakow", "kraków", "wroclaw"],
    "be": ["belgium", "brussels", "antwerp", "ghent"],
    "ch": ["switzerland", "zurich", "zürich", "geneva", "basel"],
    "es": ["spain", "madrid", "barcelona", "valencia"],
    "it": ["italy", "milan", "milano", "rome", "roma", "turin"],
    "ie": ["ireland", "dublin", "cork"],
    "pt": ["portugal", "lisbon", "lisboa", "porto"],
    "at": ["austria", "vienna", "wien"],
    "dk": ["denmark", "copenhagen"],
    "no": ["norway", "oslo"],
    "fi": ["finland", "helsinki"],
    "cz": ["czech republic", "czechia", "prague", "praha"],
    "ro": ["romania", "bucharest"],
    "hu": ["hungary", "budapest"],
    "gr": ["greece", "athens"],
    "sg": ["singapore"],
    "jp": ["japan", "tokyo", "osaka", "kyoto"],
    "cn": ["china", "beijing", "shanghai", "shenzhen"],
    "kr": ["south korea", "seoul"],
    "hk": ["hong kong"],
    "tw": ["taiwan", "taipei"],
    "ph": ["philippines", "manila"],
    "id": ["indonesia", "jakarta"],
    "vn": ["vietnam", "hanoi", "ho chi minh"],
    "th": ["thailand", "bangkok"],
    "my": ["malaysia", "kuala lumpur"],
    "mx": ["mexico", "mexico city", "guadalajara"],
    "br": ["brazil", "sao paulo", "são paulo", "rio de janeiro"],
    "ar": ["argentina", "buenos aires"],
    "co": ["colombia", "bogota", "bogotá"],
    "cl": ["chile", "santiago"],
    "za": ["south africa", "johannesburg", "cape town"],
    "il": ["israel", "tel aviv"],
    "ae": ["united arab emirates", "dubai", "abu dhabi"],
    "nz": ["new zealand", "auckland", "wellington"],
    "ru": ["russia", "moscow"],
    "ua": ["ukraine", "kyiv", "kiev"],
    "tr": ["turkey", "istanbul", "ankara"],
    "hr": ["croatia", "zagreb"],
    "rs": ["serbia", "belgrade"],
    "bg": ["bulgaria", "sofia"],
    "is": ["iceland", "reykjavik"],
    "eg": ["egypt", "cairo"],
    "pk": ["pakistan", "karachi", "lahore"],
    "bd": ["bangladesh", "dhaka"],
    "lt": ["lithuania", "vilnius"],
    "lv": ["latvia", "riga"],
    "ee": ["estonia", "tallinn"],
    "sk": ["slovakia", "bratislava"],
    "si": ["slovenia", "ljubljana"],
}


def _build_pattern(keywords: list[str]) -> re.Pattern:
    escaped = [re.escape(k) for k in keywords]
    return re.compile(r"\b(" + "|".join(escaped) + r")\b", re.IGNORECASE)


_PATTERNS: dict[str, re.Pattern] = {code: _build_pattern(kws) for code, kws in _COUNTRY_SIGNALS.items()}


def matches_country(text: str, country_code: str) -> bool:
    """True if `text` doesn't clearly rule out `country_code`.

    Postings that name the target country (or one of its major cities) are
    kept. Postings that clearly name a different country are dropped.
    Anything truly ambiguous (blank, "Remote"/"Worldwide", or nothing
    matching any known signal) is kept - favors not losing legitimate
    results over precision. Callers should pass the *full* posting text
    rather than a truncated head - relevant location info (e.g. a "Working
    mode: ... Warsaw, Poland" line) often appears well past the first few
    hundred characters.
    """
    pattern = _PATTERNS.get(country_code)
    if pattern is None:
        return True

    if pattern.search(text):
        return True

    for code, other_pattern in _PATTERNS.items():
        if code != country_code and other_pattern.search(text):
            return False

    return True
