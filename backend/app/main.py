import asyncio
import json
import logging
import queue
import re
import threading
from pathlib import Path
from typing import cast

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.config import settings
from app.country_filter import COUNTRIES, DEFAULT_COUNTRY
from app.models import MAX_SITE_RESULT_CAP, ExtractionMode, HistoryEntry, SearchRequest, SearchResult
from app.search_service import NoPostingsFoundError, run_search

DEFAULT_EXTRACTION_MODE: ExtractionMode = "claude"
EXTRACTION_MODES: set[str] = {"claude", "keyword"}
DEFAULT_SITE_RESULT_CAP = 10

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# httpx logs the full request URL (query string included) at INFO level on
# every request - several providers pass API keys as query params, so that
# would otherwise print secrets to the server log on every search.
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="Job Skill Accumulator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _validate_country(country: str) -> str:
    code = country.strip().lower()
    if code not in COUNTRIES:
        raise HTTPException(status_code=400, detail=f"Unsupported country code: {country}")
    return code


def _validate_extraction_mode(mode: str) -> ExtractionMode:
    code = mode.strip().lower()
    if code not in EXTRACTION_MODES:
        raise HTTPException(status_code=400, detail=f"Unsupported extraction mode: {mode}")
    return cast(ExtractionMode, code)


def _validate_site_result_cap(cap: int) -> int:
    if not (1 <= cap <= MAX_SITE_RESULT_CAP):
        raise HTTPException(
            status_code=400,
            detail=f"site_result_cap must be between 1 and {MAX_SITE_RESULT_CAP}",
        )
    return cap


@app.get("/api/countries")
async def countries() -> dict[str, str]:
    return COUNTRIES


@app.post("/api/search", response_model=SearchResult)
async def search(request: SearchRequest) -> SearchResult:
    job_title = request.job_title.strip()
    if not job_title:
        raise HTTPException(status_code=400, detail="job_title is required")
    country = _validate_country(request.country)
    extraction_mode = _validate_extraction_mode(request.extraction_mode)
    site_result_cap = _validate_site_result_cap(request.site_result_cap)

    try:
        return await asyncio.to_thread(
            run_search,
            job_title,
            request.limit_per_source,
            country,
            extraction_mode,
            site_result_cap,
        )
    except NoPostingsFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/search/stream")
async def search_stream(
    job_title: str,
    country: str = DEFAULT_COUNTRY,
    extraction_mode: str = DEFAULT_EXTRACTION_MODE,
    limit_per_source: int = 25,
    site_result_cap: int = DEFAULT_SITE_RESULT_CAP,
) -> StreamingResponse:
    job_title = job_title.strip()
    if not job_title:
        raise HTTPException(status_code=400, detail="job_title is required")
    country = _validate_country(country)
    extraction_mode = _validate_extraction_mode(extraction_mode)
    site_result_cap = _validate_site_result_cap(site_result_cap)

    event_queue: queue.Queue = queue.Queue()

    def worker() -> None:
        try:
            result = run_search(
                job_title,
                limit_per_source,
                country,
                extraction_mode,
                site_result_cap,
                on_progress=event_queue.put,
            )
            event_queue.put({"type": "result", "result": result.model_dump(mode="json")})
        except NoPostingsFoundError as exc:
            event_queue.put({"type": "error", "message": str(exc)})
        except Exception:
            logger.exception("Streaming search failed for %r", job_title)
            event_queue.put({"type": "error", "message": "Search failed unexpectedly"})
        finally:
            event_queue.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def event_stream():
        while True:
            item = await asyncio.to_thread(event_queue.get)
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/history", response_model=list[HistoryEntry])
async def history() -> list[HistoryEntry]:
    out_dir = Path(settings.output_dir)
    if not out_dir.exists():
        return []

    entries = []
    for json_path in out_dir.glob("*.json"):
        data = json.loads(json_path.read_text())
        entries.append(
            HistoryEntry(
                slug=data["slug"],
                job_title=data["job_title"],
                country=data.get("country", DEFAULT_COUNTRY),
                extraction_mode=data.get("extraction_mode", DEFAULT_EXTRACTION_MODE),
                site_result_cap=data.get("site_result_cap", DEFAULT_SITE_RESULT_CAP),
                generated_at=data["generated_at"],
                postings_analyzed=data["postings_analyzed"],
            )
        )
    entries.sort(key=lambda e: e.generated_at, reverse=True)
    return entries


_SLUG_PATTERN = re.compile(r"^[a-z0-9_]+$")


@app.get("/api/history/{slug}", response_model=SearchResult)
async def history_detail(slug: str) -> SearchResult:
    if not _SLUG_PATTERN.match(slug):
        raise HTTPException(status_code=400, detail="Invalid slug")

    json_path = Path(settings.output_dir) / f"{slug}.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail="Search not found")

    data = json.loads(json_path.read_text())
    txt_path = Path(settings.output_dir) / f"{slug}.txt"
    return SearchResult(
        slug=data["slug"],
        job_title=data["job_title"],
        country=data.get("country", DEFAULT_COUNTRY),
        extraction_mode=data.get("extraction_mode", DEFAULT_EXTRACTION_MODE),
        site_result_cap=data.get("site_result_cap", DEFAULT_SITE_RESULT_CAP),
        generated_at=data["generated_at"],
        postings_analyzed=data["postings_analyzed"],
        source_breakdown=data["source_breakdown"],
        site_breakdown=data.get("site_breakdown", {}),
        skills=data["skills"],
        industries=data.get("industries", []),
        postings=data.get("postings", []),
        txt_path=str(txt_path),
        json_path=str(json_path),
    )
