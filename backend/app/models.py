from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ExtractionMode = Literal["claude", "keyword"]

# Upper bound matters for cost: each Brave request page is 20 results, so a
# cap above that means extra API requests per site (15 sites x however many
# pages the cap needs). 50 caps a single search at a worst case of 15 x 3
# requests = 45 - still well within reason for a single search.
MAX_SITE_RESULT_CAP = 50


class JobPosting(BaseModel):
    title: str
    company: str | None = None
    source: str
    url: str | None = None
    description: str


class PostingLink(BaseModel):
    title: str
    company: str | None = None
    source: str
    url: str | None = None


class SkillCount(BaseModel):
    skill: str
    count: int
    percentage: float
    postings: list[PostingLink] = []


class IndustryCount(BaseModel):
    industry: str
    count: int
    percentage: float


class SearchRequest(BaseModel):
    job_title: str
    country: str = "us"
    extraction_mode: ExtractionMode = "claude"
    site_result_cap: int = Field(default=10, ge=1, le=MAX_SITE_RESULT_CAP)
    limit_per_source: int = 25


class SearchResult(BaseModel):
    slug: str
    job_title: str
    country: str
    extraction_mode: ExtractionMode
    site_result_cap: int = 10
    generated_at: datetime
    postings_analyzed: int
    source_breakdown: dict[str, str]
    site_breakdown: dict[str, int] = {}
    skills: list[SkillCount]
    industries: list[IndustryCount] = []
    postings: list[PostingLink] = []
    txt_path: str
    json_path: str


class HistoryEntry(BaseModel):
    slug: str
    job_title: str
    country: str
    extraction_mode: ExtractionMode
    site_result_cap: int = 10
    generated_at: datetime
    postings_analyzed: int
