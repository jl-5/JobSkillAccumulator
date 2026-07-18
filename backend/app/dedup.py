import re

from app.models import JobPosting

_WHITESPACE_RE = re.compile(r"\s+")


def _dedup_key(posting: JobPosting) -> tuple[str, str]:
    title = _WHITESPACE_RE.sub(" ", posting.title).strip().lower()
    company = _WHITESPACE_RE.sub(" ", posting.company or "").strip().lower()
    return (title, company)


def dedupe_postings(postings: list[JobPosting]) -> list[JobPosting]:
    """Dedup by normalized (title, company) rather than URL: some job boards
    return the exact same listing under many different URLs/IDs - a
    spam-repost pattern, not distinct jobs - so URL-based dedup alone
    misses it. Keeps first-seen order.
    """
    seen: set[tuple[str, str]] = set()
    deduped: list[JobPosting] = []
    for posting in postings:
        key = _dedup_key(posting)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(posting)
    return deduped
