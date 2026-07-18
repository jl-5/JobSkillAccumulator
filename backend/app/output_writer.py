import json
import re
from datetime import datetime
from pathlib import Path

from app.country_filter import COUNTRIES
from app.models import ExtractionMode, IndustryCount, PostingLink, SkillCount

_EXTRACTION_MODE_LABELS: dict[str, str] = {
    "claude": "Claude (AI)",
    "keyword": "Keyword matching (non-AI)",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def make_slug(job_title: str, generated_at: datetime) -> str:
    base = _SLUG_RE.sub("_", job_title.lower()).strip("_") or "search"
    timestamp = generated_at.strftime("%Y%m%d_%H%M%S")
    return f"{base}_{timestamp}"


def _render_txt(
    job_title: str,
    country: str,
    extraction_mode: ExtractionMode,
    site_result_cap: int,
    generated_at: datetime,
    postings_analyzed: int,
    source_breakdown: dict[str, str],
    site_breakdown: dict[str, int],
    skills: list[SkillCount],
    industries: list[IndustryCount],
    postings: list[PostingLink],
) -> str:
    lines = [
        "Skill Accumulation Report",
        f"Job Title/Keywords: {job_title}",
        f"Country: {COUNTRIES.get(country, country)}",
        f"Skill extraction: {_EXTRACTION_MODE_LABELS.get(extraction_mode, extraction_mode)}",
        f"Max results per site: {site_result_cap}",
        f"Generated: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Postings analyzed: {postings_analyzed}",
        "",
        "Sources:",
    ]
    for source, status in source_breakdown.items():
        lines.append(f"  - {source}: {status}")
    lines.append("")

    if site_breakdown:
        lines.append("Findings per site:")
        for site, count in sorted(site_breakdown.items(), key=lambda kv: (-kv[1], kv[0])):
            lines.append(f"  - {site}: {count}")
        lines.append("")

    if not skills:
        lines.append("No skills extracted.")
    else:
        lines.append(f"{'Rank':<6}{'Skill':<30}{'Mentions':<12}{'% of Postings':<15}")
        for rank, skill in enumerate(skills, start=1):
            lines.append(
                f"{rank:<6}{skill.skill:<30}{skill.count:<12}{skill.percentage:<15}"
            )
            for posting in skill.postings:
                label = f"{posting.title} @ {posting.company}" if posting.company else posting.title
                link = f" - {posting.url}" if posting.url else ""
                lines.append(f"        {label} ({posting.source}){link}")

    lines.append("")
    lines.append("Industries")
    lines.append("")
    if not industries:
        lines.append("No industry data.")
    else:
        lines.append(f"{'Rank':<6}{'Industry':<36}{'Postings':<12}{'% of Postings':<15}")
        for rank, industry in enumerate(industries, start=1):
            lines.append(
                f"{rank:<6}{industry.industry:<36}{industry.count:<12}{industry.percentage:<15}"
            )

    lines.append("")
    lines.append("All Postings Found (ranked by relevance)")
    lines.append("")
    if not postings:
        lines.append("No postings found.")
    else:
        for rank, posting in enumerate(postings, start=1):
            label = f"{posting.title} @ {posting.company}" if posting.company else posting.title
            link = f" - {posting.url}" if posting.url else ""
            lines.append(f"{rank:<5}{label} ({posting.source}){link}")

    return "\n".join(lines) + "\n"


def write_output(
    job_title: str,
    country: str,
    extraction_mode: ExtractionMode,
    site_result_cap: int,
    postings_analyzed: int,
    source_breakdown: dict[str, str],
    site_breakdown: dict[str, int],
    skills: list[SkillCount],
    industries: list[IndustryCount],
    postings: list[PostingLink],
    output_dir: str,
) -> tuple[str, Path, Path, datetime]:
    generated_at = datetime.now()
    slug = make_slug(job_title, generated_at)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    txt_path = out_dir / f"{slug}.txt"
    json_path = out_dir / f"{slug}.json"

    txt_path.write_text(
        _render_txt(
            job_title,
            country,
            extraction_mode,
            site_result_cap,
            generated_at,
            postings_analyzed,
            source_breakdown,
            site_breakdown,
            skills,
            industries,
            postings,
        )
    )

    json_path.write_text(
        json.dumps(
            {
                "slug": slug,
                "job_title": job_title,
                "country": country,
                "extraction_mode": extraction_mode,
                "site_result_cap": site_result_cap,
                "generated_at": generated_at.isoformat(),
                "postings_analyzed": postings_analyzed,
                "source_breakdown": source_breakdown,
                "site_breakdown": site_breakdown,
                "skills": [skill.model_dump() for skill in skills],
                "industries": [industry.model_dump() for industry in industries],
                "postings": [posting.model_dump() for posting in postings],
            },
            indent=2,
        )
    )

    return slug, txt_path, json_path, generated_at
