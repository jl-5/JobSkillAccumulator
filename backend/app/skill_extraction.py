import logging
from typing import Callable

import anthropic

from app.config import settings
from app.models import JobPosting

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[dict], None]

BATCH_SIZE = 8
MAX_DESCRIPTION_CHARS = 4000

TOOL = {
    "name": "record_skills",
    "description": (
        "Record the required/preferred skills, tools, technologies, and qualifications "
        "extracted from each job posting in this batch."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "posting_index": {
                            "type": "integer",
                            "description": "The index of the posting this result corresponds to.",
                        },
                        "skills": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Concise, normalized skill names (e.g. 'Python', 'AWS', "
                                "'Communication'). No duplicates."
                            ),
                        },
                    },
                    "required": ["posting_index", "skills"],
                },
            }
        },
        "required": ["results"],
    },
}

SYSTEM_PROMPT = (
    "You are extracting required and preferred skills from job postings. "
    "For each posting, list the concrete skills, tools, technologies, certifications, "
    "and qualifications it asks for. Normalize similar terms to a common form "
    "(e.g. 'JS' -> 'JavaScript', 'communication skills' -> 'Communication'). "
    "Keep each skill name short (1-4 words). Do not invent skills that aren't implied "
    "by the text. Call the record_skills tool with one entry per posting index provided."
)


def _build_batch_prompt(batch: list[tuple[int, JobPosting]]) -> str:
    parts = []
    for index, posting in batch:
        description = posting.description[:MAX_DESCRIPTION_CHARS]
        parts.append(
            f"### Posting {index}\nTitle: {posting.title}\n"
            f"Company: {posting.company or 'Unknown'}\n"
            f"Description:\n{description}"
        )
    return "\n\n".join(parts)


def extract_skills(
    postings: list[JobPosting], on_progress: ProgressCallback | None = None
) -> list[list[str]]:
    """Returns a list parallel to `postings`, each entry a list of extracted skills.
    Postings whose batch failed to extract get an empty list rather than aborting the run.
    """
    results: list[list[str]] = [[] for _ in postings]
    if not postings:
        return results

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    indexed = list(enumerate(postings))
    total_batches = (len(indexed) + BATCH_SIZE - 1) // BATCH_SIZE

    if on_progress is not None:
        on_progress({"type": "extracting_start", "postings": len(postings), "total_batches": total_batches})

    for batch_num, start in enumerate(range(0, len(indexed), BATCH_SIZE), start=1):
        try:
            batch = indexed[start : start + BATCH_SIZE]
            prompt = _build_batch_prompt(batch)
            try:
                response = client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=2048,
                    system=SYSTEM_PROMPT,
                    tools=[TOOL],
                    tool_choice={"type": "tool", "name": "record_skills"},
                    messages=[{"role": "user", "content": prompt}],
                )
            except Exception:
                logger.exception("Skill extraction batch failed at offset %s", start)
                continue

            tool_use = next(
                (block for block in response.content if block.type == "tool_use"), None
            )
            if tool_use is None:
                logger.warning("No tool_use block in response for batch at offset %s", start)
                continue

            for item in tool_use.input.get("results", []):
                index = item.get("posting_index")
                skills = item.get("skills", [])
                if isinstance(index, int) and 0 <= index < len(results):
                    results[index] = [s.strip() for s in skills if isinstance(s, str) and s.strip()]
        finally:
            if on_progress is not None:
                on_progress({"type": "extracting_progress", "completed": batch_num, "total": total_batches})

    return results
