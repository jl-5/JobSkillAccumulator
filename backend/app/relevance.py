from app.models import JobPosting
from app.providers.matching import split_terms

TITLE_TERM_WEIGHT = 3
DESCRIPTION_TERM_WEIGHT = 1
EXACT_PHRASE_BONUS = 10
DESCRIPTION_SCAN_CHARS = 1000


def _score(query_terms: list[str], phrase: str, posting: JobPosting) -> float:
    title = posting.title.lower()
    description_head = posting.description[:DESCRIPTION_SCAN_CHARS].lower()

    score = 0.0
    if phrase and phrase in title:
        score += EXACT_PHRASE_BONUS
    score += sum(TITLE_TERM_WEIGHT for term in query_terms if term in title)
    score += sum(DESCRIPTION_TERM_WEIGHT for term in query_terms if term in description_head)
    return score


def rank_by_relevance(query: str, postings: list[JobPosting]) -> list[JobPosting]:
    """Sort postings by relevance to `query`: title match weighted highest,
    then description mentions. Expects `postings` to already be deduped
    (see `app.dedup.dedupe_postings`).
    """
    query_terms = split_terms(query)
    phrase = query.strip().lower()
    return sorted(postings, key=lambda p: _score(query_terms, phrase, p), reverse=True)
