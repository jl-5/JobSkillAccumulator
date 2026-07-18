import httpx

from app.config import settings
from app.providers.ats_search_base import (
    ATS_DOMAINS,
    SITE_RESTRICT,
    ATSSearchProvider,
    platform_names_for,
    url_matches_domains,
)
from app.providers.base import ProgressCallback

SEARCH_URL = "https://www.googleapis.com/customsearch/v1"
PAGE_SIZE = 10
MAX_RESULTS = 50  # keeps daily CSE quota usage (100 free queries/day) in check


class GoogleJobsProvider(ATSSearchProvider):
    name = "Google (ATS boards)"

    def is_configured(self) -> bool:
        return bool(settings.google_cse_api_key and settings.google_cse_id)

    def _search(
        self,
        query: str,
        limit: int,
        country: str,
        site_result_cap: int | None = None,
        on_progress: ProgressCallback | None = None,
    ) -> list[dict]:
        # Google isn't chunked per-site (single combined query for all
        # domains), so site_result_cap doesn't apply here - accepted only to
        # keep the _search() signature consistent with ATSSearchProvider.
        if on_progress is not None:
            on_progress(
                {
                    "type": "provider_progress",
                    "source": self.name,
                    "detail": f"Checking {platform_names_for(ATS_DOMAINS)}",
                }
            )

        items: list[dict] = []
        start = 1
        while len(items) < min(limit, MAX_RESULTS) and start <= 91:
            try:
                response = httpx.get(
                    SEARCH_URL,
                    params={
                        "key": settings.google_cse_api_key,
                        "cx": settings.google_cse_id,
                        "q": f'"{query}" {SITE_RESTRICT}',
                        "num": PAGE_SIZE,
                        "start": start,
                        "gl": country,
                    },
                    timeout=15.0,
                )
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                # Don't let the exception's default str() (which includes the
                # full request URL, API key included) leak up to callers.
                raise RuntimeError(
                    f"Google Custom Search request failed with HTTP {exc.response.status_code}"
                ) from None
            except httpx.HTTPError as exc:
                raise RuntimeError(f"Google Custom Search request failed: {type(exc).__name__}") from None

            page_items = response.json().get("items", [])
            if not page_items:
                break
            # Google's site: operator is a ranking hint, not a hard filter -
            # see url_matches_domains for the empirical basis (same
            # behavior confirmed on Brave; not yet re-verified against
            # Google's live API since this provider is dormant).
            items.extend(
                {"title": i.get("title"), "url": i.get("link")}
                for i in page_items
                if i.get("link") and url_matches_domains(i["link"], ATS_DOMAINS)
            )
            start += PAGE_SIZE
        return items[:limit]
