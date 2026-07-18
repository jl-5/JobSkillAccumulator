import json
import logging
import re
import threading
from pathlib import Path

from app.config import settings
from app.models import JobPosting

logger = logging.getLogger(__name__)

# canonical skill name -> literal text variants to match against posting text.
# Ambiguous short/common-English-word variants (bare "go", "r", "c", "spark",
# "node") are deliberately left out even where they'd be the natural
# abbreviation - keyword matching has no semantic understanding, so a common
# word masquerading as a language/tool name would produce heavy false-positive
# noise. This is the accepted trade-off of the non-AI mode: fast and free,
# but lower precision than the Claude-based extractor.
SKILLS: dict[str, list[str]] = {
    "Python": ["python"],
    "JavaScript": ["javascript", "js"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp", "c sharp"],
    "Go": ["golang"],
    "Rust": ["rust"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "SQL": ["sql"],
    "Bash": ["bash", "shell scripting"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Perl": ["perl"],
    "MATLAB": ["matlab"],
    "Objective-C": ["objective-c", "objective c"],
    "React": ["react.js", "react"],
    "Vue": ["vue.js", "vue"],
    "Angular": ["angular.js", "angularjs", "angular"],
    "Svelte": ["svelte"],
    "Next.js": ["next.js", "nextjs"],
    "jQuery": ["jquery"],
    "Redux": ["redux"],
    "Tailwind CSS": ["tailwind css", "tailwindcss", "tailwind"],
    "Webpack": ["webpack"],
    "Vite": ["vite"],
    "Node.js": ["node.js", "nodejs"],
    "Express": ["express.js", "expressjs", "express"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring Boot": ["spring boot", "springboot"],
    "Spring": ["spring framework"],
    "Ruby on Rails": ["ruby on rails", "rails"],
    "ASP.NET": ["asp.net", "aspnet"],
    "Laravel": ["laravel"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest api", "restful api", "rest apis"],
    "gRPC": ["grpc"],
    "PostgreSQL": ["postgresql", "postgres"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "SQLite": ["sqlite"],
    "Oracle Database": ["oracle database", "oracle db"],
    "SQL Server": ["sql server", "mssql"],
    "DynamoDB": ["dynamodb"],
    "Cassandra": ["cassandra"],
    "Elasticsearch": ["elasticsearch"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["azure"],
    "GCP": ["gcp", "google cloud platform", "google cloud"],
    "Docker": ["docker"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "Ansible": ["ansible"],
    "Jenkins": ["jenkins"],
    "CI/CD": ["ci/cd", "continuous integration", "continuous deployment"],
    "GitHub Actions": ["github actions"],
    "GitLab CI": ["gitlab ci"],
    "CloudFormation": ["cloudformation"],
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning"],
    "TensorFlow": ["tensorflow"],
    "PyTorch": ["pytorch"],
    "Pandas": ["pandas"],
    "NumPy": ["numpy"],
    "Scikit-learn": ["scikit-learn", "sklearn"],
    "Data Science": ["data science"],
    "NLP": ["nlp", "natural language processing"],
    "LLMs": ["llm", "llms", "large language model"],
    "Apache Spark": ["apache spark", "pyspark"],
    "Airflow": ["airflow"],
    "Kafka": ["kafka"],
    "ETL": ["etl"],
    "Data Engineering": ["data engineering"],
    "Tableau": ["tableau"],
    "Power BI": ["power bi", "powerbi"],
    "Looker": ["looker"],
    "Git": ["git"],
    "Agile": ["agile"],
    "Scrum": ["scrum"],
    "Jira": ["jira"],
    "Confluence": ["confluence"],
    "TDD": ["tdd", "test-driven development"],
    "Unit Testing": ["unit testing", "unit tests"],
    "Microservices": ["microservices", "microservice architecture"],
    "DevOps": ["devops"],
    "Linux": ["linux"],
    "System Design": ["system design"],
    "OAuth": ["oauth"],
    "Communication": ["communication skills", "communication"],
    "Leadership": ["leadership"],
    "Problem Solving": ["problem solving", "problem-solving"],
    "Teamwork": ["teamwork"],
    "Collaboration": ["collaboration"],
    "Project Management": ["project management"],
    "Time Management": ["time management"],
    "Critical Thinking": ["critical thinking"],
    "Mentoring": ["mentoring", "mentorship"],
    "iOS": ["ios development", "ios"],
    "Android": ["android development", "android"],
    "React Native": ["react native"],
    "Flutter": ["flutter"],
    "SwiftUI": ["swiftui"],
    "Figma": ["figma"],
    "UI/UX": ["ui/ux", "ux/ui", "user experience design"],
    "Adobe Photoshop": ["adobe photoshop", "photoshop"],
    "Sketch": ["sketch app"],
    "PMP": ["pmp", "project management professional"],
    "CPA": ["cpa", "certified public accountant"],
    "Six Sigma": ["six sigma"],
    "CISSP": ["cissp"],
}


def _learned_skills_path() -> Path:
    return Path(settings.learned_skills_path)


def _load_learned_skills() -> dict[str, list[str]]:
    path = _learned_skills_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("Could not read learned skills file at %s, starting fresh", path)
        return {}


def _save_learned_skills(learned: dict[str, list[str]]) -> None:
    path = _learned_skills_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(learned, indent=2, sort_keys=True))


def _build_pattern(skills: dict[str, list[str]]) -> tuple[re.Pattern, dict[str, str]]:
    alias_to_canonical: dict[str, str] = {}
    for canonical, variants in skills.items():
        for variant in variants:
            alias_to_canonical[variant.lower()] = canonical

    # Longest first so overlapping variants (e.g. "c#" vs a hypothetical
    # shorter prefix) prefer the more specific match.
    variants_by_length = sorted(alias_to_canonical.keys(), key=len, reverse=True)
    escaped = [re.escape(v) for v in variants_by_length]
    # (?<!\w)...(?!\w) instead of \b: \b fails to bound tokens that end in a
    # non-word character (e.g. "C++" followed by a space has no \w/\W
    # transition at the trailing "+"), which plain word-boundary matching
    # would silently miss.
    pattern = re.compile(r"(?<!\w)(" + "|".join(escaped) + r")(?!\w)", re.IGNORECASE)
    return pattern, alias_to_canonical


_lock = threading.Lock()
_learned_skills: dict[str, list[str]] = _load_learned_skills()
_PATTERN, _ALIAS_TO_CANONICAL = _build_pattern({**SKILLS, **_learned_skills})


def extract_skills_keyword(postings: list[JobPosting]) -> list[list[str]]:
    """Non-AI alternative to Claude-based extraction: matches posting text
    against a curated skills dictionary. Faster and free, but lower recall/
    precision than semantic extraction - only catches skills phrased close
    to a known variant, and can't infer skills implied by the text.
    """
    results: list[list[str]] = []
    for posting in postings:
        haystack = f"{posting.title} {posting.description}"
        found: set[str] = set()
        for match in _PATTERN.finditer(haystack):
            canonical = _ALIAS_TO_CANONICAL.get(match.group(0).lower())
            if canonical:
                found.add(canonical)
        results.append(sorted(found))
    return results


def learn_skills_from_claude(skill_names: list[str]) -> int:
    """Add any skill names Claude extracted that the keyword matcher doesn't
    already recognize, persisting them to `settings.learned_skills_path` so
    future keyword-mode searches catch them too. Returns how many were new.
    """
    global _PATTERN, _ALIAS_TO_CANONICAL

    with _lock:
        new_entries: dict[str, list[str]] = {}
        seen_lower = set(_ALIAS_TO_CANONICAL.keys())
        for name in skill_names:
            key = name.strip()
            if not key or key.lower() in seen_lower:
                continue
            seen_lower.add(key.lower())
            new_entries[key] = [key.lower()]

        if not new_entries:
            return 0

        _learned_skills.update(new_entries)
        _save_learned_skills(_learned_skills)
        _PATTERN, _ALIAS_TO_CANONICAL = _build_pattern({**SKILLS, **_learned_skills})

    logger.info("Learned %d new skill(s) from Claude: %s", len(new_entries), ", ".join(sorted(new_entries)))
    return len(new_entries)
