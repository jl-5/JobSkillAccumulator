from collections import Counter

from app.models import JobPosting, PostingLink, SkillCount


def aggregate_skills(
    postings: list[JobPosting], skills_per_posting: list[list[str]]
) -> list[SkillCount]:
    total = len(skills_per_posting)
    if total == 0:
        return []

    counts: Counter[str] = Counter()
    display_forms: dict[str, str] = {}
    postings_by_skill: dict[str, list[PostingLink]] = {}

    for posting, skills in zip(postings, skills_per_posting):
        seen_this_posting: set[str] = set()
        for skill in skills:
            key = skill.lower().strip()
            if not key or key in seen_this_posting:
                continue
            seen_this_posting.add(key)
            counts[key] += 1
            display_forms.setdefault(key, skill.strip())
            postings_by_skill.setdefault(key, []).append(
                PostingLink(
                    title=posting.title,
                    company=posting.company,
                    source=posting.source,
                    url=posting.url,
                )
            )

    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], display_forms[kv[0]].lower()))
    return [
        SkillCount(
            skill=display_forms[key],
            count=count,
            percentage=round(count / total * 100, 1),
            postings=postings_by_skill[key],
        )
        for key, count in ranked
    ]
