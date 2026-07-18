import logging
from urllib.parse import parse_qs, urlparse

import httpx

from app.country_filter import matches_country
from app.models import JobPosting
from app.providers.base import JobProvider, ProgressCallback
from app.providers.htmlutil import strip_html

logger = logging.getLogger(__name__)

# ATS platforms whose posting pages were verified (empirically - by fetching
# real live postings with no JS execution and checking the description text
# actually came through in the raw HTML) to be plain server-rendered.
# Excluded despite appearing in briansjobsearch.com's own site list because
# they render via client-side JS and return an empty shell to a plain HTTP
# fetch: Workday, Ashby, Workable, iCIMS, ADP, Rippling, Dover, Dayforce,
# Gem, Oracle Cloud, CareerPuck. Also excluded: LinkedIn/Glassdoor (ToS
# prohibits scraping) and Wellfound/BuiltIn/Work-at-a-Startup/Remote
# Rocketship (consumer job-board aggregators, same category as LinkedIn/
# Indeed rather than a company's own ATS-hosted postings). Brian's generic
# wildcard categories (careers.*, jobs.*, people.*, talent.*) can't be
# replicated at all since they rely on whole-web search, which Google
# discontinued for new Programmable Search Engines in Jan 2026 - a
# site-restricted engine can only match domains explicitly listed in it.
ATS_DOMAINS = [
    # Bare "greenhouse.io" rather than a specific subdomain: Greenhouse has
    # hosted postings on boards.greenhouse.io (legacy), job-boards.greenhouse.io
    # (current default), and job-boards.eu.greenhouse.io (EU) at various
    # points - pinning to one subdomain silently lost most current postings
    # when Greenhouse switched defaults. site:greenhouse.io matches all of
    # them (verified empirically) and is robust to any future rename.
    "greenhouse.io",
    "jobs.lever.co",
    "recruitee.com",
    "jobs.smartrecruiters.com",
    "recruiting.paylocity.com",
    "jobs.gusto.com",
    "jobs.personio.com",
    "catsone.com",
    "trinethire.com",
    "teamtailor.com",
    "pinpointhq.com",
    "jobs.jobvite.com",
    "jobappnetwork.com",
    "breezy.hr",
    "applytojob.com",
]


# Friendly per-platform names for the JobPosting.source field, so postings
# found via Google/Brave show which ATS actually hosts them ("Greenhouse",
# "Lever", ...) rather than a generic "Google (ATS boards)" / "Brave Search
# (ATS boards)" label that just says which search API found it.
ATS_PLATFORM_NAMES: dict[str, str] = {
    "greenhouse.io": "Greenhouse",
    "jobs.lever.co": "Lever",
    "recruitee.com": "Recruitee",
    "jobs.smartrecruiters.com": "SmartRecruiters",
    "recruiting.paylocity.com": "Paylocity",
    "jobs.gusto.com": "Gusto",
    "jobs.personio.com": "Personio",
    "catsone.com": "CATS",
    "trinethire.com": "TriNet Hire",
    "teamtailor.com": "Teamtailor",
    "pinpointhq.com": "Pinpoint",
    "jobs.jobvite.com": "Jobvite",
    "jobappnetwork.com": "TalentReef",
    "breezy.hr": "BreezyHR",
    "applytojob.com": "JazzHR",
}


def _infer_platform(url: str) -> str | None:
    hostname = (urlparse(url).hostname or "").lower()
    for domain, name in ATS_PLATFORM_NAMES.items():
        if hostname == domain or hostname.endswith(f".{domain}"):
            return name
    return None


def url_matches_domains(url: str, domains: list[str]) -> bool:
    """Whether url's hostname actually belongs to one of domains.

    Search APIs treat `site:` as a ranking hint, not a hard filter: a niche
    query with few/no real matches on the requested domain gets backfilled
    with unrelated general-web results (LinkedIn/Glassdoor/Indeed search
    pages, stale cached listings on sites outside ATS_DOMAINS entirely,
    ...) instead of returning nothing. Verified empirically - a
    `site:jobs.smartrecruiters.com` query for a niche title returned
    linkedin.com, glassdoor.com, ziprecruiter.com, reddit.com and a
    third-party careers page, none of which are on that domain. Every
    result must be checked against the domain(s) it was actually queried
    for before being treated as a real posting.
    """
    hostname = (urlparse(url).hostname or "").lower()
    return any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains)


def platform_names_for(domains: list[str]) -> str:
    """Friendly, comma-separated platform names for a list of ATS_DOMAINS
    entries - used to describe what a sub-query is checking in progress
    updates (e.g. "Greenhouse, Lever, Recruitee")."""
    return ", ".join(ATS_PLATFORM_NAMES.get(d, d) for d in domains)


def build_site_restrict(domains: list[str]) -> str:
    return "(" + " OR ".join(f"site:{domain}" for domain in domains) + ")"


def chunk_domains(domains: list[str], size: int) -> list[list[str]]:
    return [domains[i : i + size] for i in range(0, len(domains), size)]


SITE_RESTRICT = build_site_restrict(ATS_DOMAINS)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

MIN_DESCRIPTION_CHARS = 200

# Common phrasing ATS platforms use on a posting's page once it's been
# pulled down - a fetch can still return HTTP 200 with a generic "this job
# is gone" page instead of the actual description, which would otherwise
# get included as a normal (stale, dead-link) result.
_CLOSED_POSTING_SIGNALS = [
    "this job has expired",
    "this position is no longer available",
    "no longer accepting applications",
    "no longer accepting candidates",
    "this job posting is no longer active",
    "this posting is no longer active",
    "this position has been filled",
    "job is no longer accepting",
    "there are no current openings",
]

# Query-string markers ATS platforms attach when redirecting a dead job ID
# to their own fallback page - confirmed empirically on Greenhouse
# (.../<company>/jobs/<id> -> .../<company>?error=true) and Jobvite
# (.../<company>/job/<id> -> www.jobvite.com/support/...?invalid=1).
_DEAD_REDIRECT_QUERY_SIGNALS = {"error", "invalid"}


def _redirected_to_generic_page(original_url: str, final_url: str) -> bool:
    """Whether a job-specific URL got redirected to a company's general
    board/listing page, or the ATS vendor's own fallback page, instead of
    the platform returning a 404 for an expired job ID. Both confirmed
    fallback destinations return HTTP 200 with substantial real-looking
    text (a list of the company's *other* current openings, or the
    vendor's generic support page), so neither MIN_DESCRIPTION_CHARS nor
    _CLOSED_POSTING_SIGNALS reliably catches them - the redirect itself is
    the only unambiguous signal.
    """
    final_parsed = urlparse(final_url)
    if set(parse_qs(final_parsed.query)) & _DEAD_REDIRECT_QUERY_SIGNALS:
        return True

    original_path = urlparse(original_url).path.rstrip("/")
    final_path = final_parsed.path.rstrip("/")
    return final_path != original_path and original_path.startswith(f"{final_path}/")

# Subdomains that are the ATS's own generic hostname rather than a specific
# company (e.g. boards.greenhouse.io/openrouter/... - "boards" isn't the
# company, "openrouter" in the path is).
_GENERIC_SUBDOMAINS = {
    "jobs", "careers", "career", "apply", "boards", "job-boards", "www",
    "recruiting", "myjobs", "workforcenow", "app", "hire", "cf-apply",
}


def _infer_company(url: str) -> str | None:
    parsed = urlparse(url)
    labels = parsed.hostname.split(".") if parsed.hostname else []
    if len(labels) > 2 and labels[0] not in _GENERIC_SUBDOMAINS:
        return labels[0].replace("-", " ").title()

    parts = [p for p in parsed.path.split("/") if p]
    return parts[0].replace("-", " ").title() if parts else None


class ATSSearchProvider(JobProvider):
    """Base for providers that discover ATS job postings via a site-restricted
    web search (limited to `ATS_DOMAINS`), then fetch each posting's page
    directly for its full description. Subclasses implement `_search()`
    against a specific search API; the domain list and posting-fetch/
    country-filter logic are shared so multiple search backends (Google,
    Brave, ...) don't duplicate it.
    """

    def _search(
        self,
        query: str,
        limit: int,
        country: str,
        site_result_cap: int | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[dict]:
        """Return up to `limit` results as [{"title": ..., "url": ...}, ...]."""
        raise NotImplementedError

    def _fetch_description(self, url: str, country: str, search_title: str = "") -> str | None:
        try:
            response = httpx.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=15.0, follow_redirects=True
            )
            response.raise_for_status()
        except httpx.HTTPError:
            logger.warning("Failed to fetch posting page %s", url)
            return None

        if _redirected_to_generic_page(url, str(response.url)):
            return None

        text = strip_html(response.text)
        if len(text) < MIN_DESCRIPTION_CHARS:
            return None

        lowered = text.lower()
        if any(signal in lowered for signal in _CLOSED_POSTING_SIGNALS):
            return None

        # Scans the full text, not just the head: location info (e.g. a
        # "Working mode: ... Warsaw, Poland" line) often appears well past
        # the first few hundred characters, and missing it is a worse
        # failure (a non-target-country posting silently included) than the
        # rarer false exclusion from an incidental later mention. The search
        # engine's own result title is included too - Brave/Google sometimes
        # synthesize a location-bearing title (e.g. "... in Montréal, QC,
        # Canada") from page metadata that never appears in the visible,
        # scraped page body itself.
        if not matches_country(f"{search_title} {text}", country):
            return None
        return text

    def fetch(
        self,
        query: str,
        limit: int,
        country: str,
        site_result_cap: int | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[JobPosting]:
        results = self._search(query, limit, country, site_result_cap, on_progress)

        postings: list[JobPosting] = []
        for item in results:
            url = item.get("url")
            title = item.get("title")
            if not url or not title:
                continue
            description = self._fetch_description(url, country, search_title=title)
            if not description:
                continue
            postings.append(
                JobPosting(
                    title=title,
                    company=_infer_company(url),
                    source=_infer_platform(url) or self.name,
                    url=url,
                    description=description,
                )
            )
        return postings
