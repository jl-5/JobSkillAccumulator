import httpx

from app.config import settings
from app.defense_filter import is_defense_related
from app.models import JobPosting
from app.providers.ats_search_base import (
    ATS_DOMAINS,
    ATSSearchProvider,
    build_site_restrict,
    chunk_domains,
    platform_names_for,
    url_matches_domains,
)
from app.providers.base import ProgressCallback

SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
PAGE_SIZE = 20  # Brave's max results per page
MAX_OFFSET = 9  # 0-based page offset, Brave's max - up to 10 pages

# Default per-site cap, used when the caller doesn't pass its own
# site_result_cap (e.g. the UI's "max results per site" input - see
# SearchRequest.site_result_cap). Each site's own contribution is capped
# independently, rather than the whole search stopping once *any* site
# fills the overall limit - Greenhouse alone regularly has enough matches to
# satisfy a typical limit (e.g. 25) by itself, which meant every other site
# never even got queried. Values <= PAGE_SIZE cost exactly one request per
# site; above that, _search_group pages further (one extra request per
# additional PAGE_SIZE chunk), so a high cap directly costs more Brave API
# calls - 15 sites x ceil(cap / PAGE_SIZE) requests per search.
SITE_RESULT_CAP = 10

# One ATS domain queried at a time - lets progress show each site
# individually and mark it done as its own query completes, rather than a
# batch of several flipping to "done" together. Costs more Brave API calls
# than grouping several domains per query (previously 5 at a time), since
# Brave enforces a 400-char cap on the whole "q" string that a multi-domain
# OR-list can exceed for long job titles anyway - querying one domain at a
# time sidesteps that limit entirely as a side effect.
DOMAIN_GROUP_SIZE = 1
_DOMAIN_GROUPS = chunk_domains(ATS_DOMAINS, DOMAIN_GROUP_SIZE)


class BraveSearchProvider(ATSSearchProvider):
    name = "Brave Search (ATS boards)"

    def is_configured(self) -> bool:
        return bool(settings.brave_search_api_key)

    def _search_group(self, query: str, domains: list[str], limit: int, country: str) -> list[dict]:
        site_restrict = build_site_restrict(domains)
        items: list[dict] = []
        offset = 0
        while len(items) < limit and offset <= MAX_OFFSET:
            try:
                response = httpx.get(
                    SEARCH_URL,
                    headers={
                        "Accept": "application/json",
                        "X-Subscription-Token": settings.brave_search_api_key,
                    },
                    params={
                        "q": f'"{query}" {site_restrict}',
                        "count": PAGE_SIZE,
                        "offset": offset,
                        "country": country,
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # Don't let the exception's default str() (which includes the
                # full request URL) leak up to callers. Brave sends the key
                # as a header rather than a query param, but keep this
                # consistent with the other search providers regardless.
                raise RuntimeError(
                    f"Brave Search request failed with HTTP {exc.response.status_code}"
                ) from None
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Brave Search request failed: {type(exc).__name__}") from None

            page_items = response.json().get("web", {}).get("results", [])
            if not page_items:
                break
            # Brave's site: operator is a ranking hint, not a hard filter -
            # a query with few/no real matches gets backfilled with
            # unrelated general-web results instead of returning nothing.
            # Drop anything not actually hosted on the requested domain(s).
            matched = [
                {"title": i.get("title"), "url": i.get("url")}
                for i in page_items
                if i.get("url") and url_matches_domains(i["url"], domains)
            ]
            if not matched:
                # Real matches rank before backfill, so a page with none
                # means we've hit the junk zone - further pages are just
                # more backfill, not worth the extra request.
                break
            items.extend(matched)
            offset += 1
        return items

    def fetch(
        self,
        query: str,
        limit: int,
        country: str,
        site_result_cap: int | None = None,
        exclude_defense: bool = False,
        on_progress: ProgressCallback | None = None,
    ) -> list[JobPosting]:
        # Overrides ATSSearchProvider.fetch() rather than implementing
        # _search(): each site's postings are fetched and filtered (country,
        # closed/expired, dead-redirect) immediately after searching it,
        # before moving to the next site, so site_done's count is the real
        # number of usable postings found there - not the raw search-hit
        # count, most of which typically doesn't survive filtering. `limit`
        # (limit_per_source) is accepted for interface consistency but
        # unused: site_result_cap is the only depth control now, since a
        # combined cap applied by domain list order previously meant sites
        # queried later (Lever, Recruitee, ...) could silently end up with
        # zero fetched postings whenever an earlier site alone reached the
        # combined cap, despite showing a nonzero raw count live.
        cap = site_result_cap if site_result_cap is not None else SITE_RESULT_CAP

        if on_progress is not None:
            on_progress(
                {
                    "type": "provider_sites",
                    "source": self.name,
                    "sites": [platform_names_for([d]) for d in ATS_DOMAINS],
                }
            )

        postings: list[JobPosting] = []
        for group in _DOMAIN_GROUPS:
            site_name = platform_names_for(group)

            if on_progress is not None:
                on_progress({"type": "site_start", "source": self.name, "site": site_name})

            found = self._search_group(query, group, cap, country)[:cap]

            site_postings: list[JobPosting] = []
            for item in found:
                url = item.get("url")
                title = item.get("title")
                if not url or not title:
                    continue
                description = self._fetch_description(url, country, search_title=title)
                if not description:
                    continue
                posting = self._build_posting(url, title, description)
                if exclude_defense and is_defense_related(f"{title} {description}", posting.company):
                    continue
                site_postings.append(posting)

            postings.extend(site_postings)

            if on_progress is not None:
                on_progress(
                    {
                        "type": "site_done",
                        "source": self.name,
                        "site": site_name,
                        "count": len(site_postings),
                    }
                )
        return postings
