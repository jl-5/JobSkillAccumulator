import logging
import re
from typing import Callable

from app.aggregator import aggregate_skills
from app.config import settings
from app.country_filter import DEFAULT_COUNTRY
from app.dedup import dedupe_postings
from app.industry_classification import aggregate_industries
from app.keyword_extraction import extract_skills_keyword, learn_skills_from_claude
from app.models import ExtractionMode, JobPosting, PostingLink, SearchResult
from app.output_writer import write_output
from app.relevance import rank_by_relevance
from app.providers.base import JobProvider
from app.providers.brave_jobs import SITE_RESULT_CAP as DEFAULT_SITE_RESULT_CAP
from app.providers.brave_jobs import BraveSearchProvider

# GoogleJobsProvider is kept in the codebase (app/providers/google_jobs.py)
# but left out of active rotation - persistent account-level 403 from
# Google Cloud (see README "Sources" section). Re-add
# `GoogleJobsProvider()` below once that's resolved.
from app.skill_extraction import extract_skills

logger = logging.getLogger(__name__)

PROVIDERS: list[JobProvider] = [
    BraveSearchProvider(),
]

ProgressCallback = Callable[[dict], None]


class NoPostingsFoundError(Exception):
    pass


def _emit(on_progress: ProgressCallback | None, event: dict) -> None:
    if on_progress is not None:
        on_progress(event)


def _tracking_progress(
    site_breakdown: dict[str, int], on_progress: ProgressCallback | None
) -> ProgressCallback:
    """Wraps on_progress to also accumulate each site_done event's count into
    site_breakdown, so the per-site findings shown live during the search
    can also be included in the final persisted result."""

    def wrapped(event: dict) -> None:
        if event.get("type") == "site_done":
            site = event.get("site")
            if site:
                site_breakdown[site] = site_breakdown.get(site, 0) + event.get("count", 0)
        _emit(on_progress, event)

    return wrapped


# Safety net: an exception's default str() can include the full request URL
# a provider was hit with, and several providers pass secrets as query
# params. Redact anything that looks like one before it reaches
# source_breakdown, which is shown in the UI and persisted to disk.
_SECRET_PARAM_RE = re.compile(
    r"(?i)\b(key|token|secret|password|app_key|api_key|app_id|access_token)=[^&\s'\"]+"
)


def _sanitize_error(exc: Exception) -> str:
    return _SECRET_PARAM_RE.sub(r"\1=REDACTED", str(exc))


def run_search(
    job_title: str,
    limit_per_source: int = 25,
    country: str = DEFAULT_COUNTRY,
    extraction_mode: ExtractionMode = "claude",
    site_result_cap: int | None = None,
    on_progress: ProgressCallback | None = None,
) -> SearchResult:
    postings: list[JobPosting] = []
    source_breakdown: dict[str, str] = {}
    site_breakdown: dict[str, int] = {}
    resolved_site_result_cap = site_result_cap if site_result_cap is not None else DEFAULT_SITE_RESULT_CAP

    _emit(on_progress, {"type": "start", "sources": [p.name for p in PROVIDERS]})

    for provider in PROVIDERS:
        if not provider.is_configured():
            source_breakdown[provider.name] = "skipped (not configured)"
            _emit(
                on_progress,
                {"type": "provider_done", "source": provider.name, "status": source_breakdown[provider.name]},
            )
            continue

        _emit(on_progress, {"type": "provider_start", "source": provider.name})
        try:
            fetched = provider.fetch(
                job_title,
                limit_per_source,
                country,
                site_result_cap=site_result_cap,
                on_progress=_tracking_progress(site_breakdown, on_progress),
            )
        except Exception as exc:
            logger.exception("Provider %s failed", provider.name)
            source_breakdown[provider.name] = f"error: {_sanitize_error(exc)}"
            _emit(
                on_progress,
                {"type": "provider_done", "source": provider.name, "status": source_breakdown[provider.name]},
            )
            continue

        postings.extend(fetched)
        source_breakdown[provider.name] = f"{len(fetched)} postings"
        _emit(
            on_progress,
            {"type": "provider_done", "source": provider.name, "status": source_breakdown[provider.name]},
        )

    if not postings:
        raise NoPostingsFoundError(
            f"No job postings found for '{job_title}' across configured sources."
        )

    postings = dedupe_postings(postings)

    if extraction_mode == "claude":
        skills_per_posting = extract_skills(postings, on_progress=on_progress)
    else:
        _emit(on_progress, {"type": "extracting_start", "postings": len(postings), "total_batches": 1})
        skills_per_posting = extract_skills_keyword(postings)
        _emit(on_progress, {"type": "extracting_progress", "completed": 1, "total": 1})
    skills = aggregate_skills(postings, skills_per_posting)

    if extraction_mode == "claude":
        learned_count = learn_skills_from_claude([skill.skill for skill in skills])
        if learned_count:
            _emit(on_progress, {"type": "learned_skills", "count": learned_count})

    ranked_postings = rank_by_relevance(job_title, postings)
    posting_links = [
        PostingLink(title=p.title, company=p.company, source=p.source, url=p.url)
        for p in ranked_postings
    ]

    industries = aggregate_industries(postings)

    slug, txt_path, json_path, generated_at = write_output(
        job_title=job_title,
        country=country,
        extraction_mode=extraction_mode,
        site_result_cap=resolved_site_result_cap,
        postings_analyzed=len(postings),
        source_breakdown=source_breakdown,
        site_breakdown=site_breakdown,
        skills=skills,
        industries=industries,
        postings=posting_links,
        output_dir=settings.output_dir,
    )

    return SearchResult(
        slug=slug,
        job_title=job_title,
        country=country,
        extraction_mode=extraction_mode,
        site_result_cap=resolved_site_result_cap,
        generated_at=generated_at,
        postings_analyzed=len(postings),
        source_breakdown=source_breakdown,
        site_breakdown=site_breakdown,
        skills=skills,
        industries=industries,
        postings=posting_links,
        txt_path=str(txt_path),
        json_path=str(json_path),
    )
