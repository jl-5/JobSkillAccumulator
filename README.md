# JobSkillAccumulator

Enter a job title or keywords, and the app pulls current job postings for it from
public job APIs, extracts the skills each posting asks for, and shows a ranked
"most commonly requested skills" report. Each search also writes a report to
`backend/output/<job-title>_<timestamp>.txt`.

## Features

- **Live progress while searching** — a progress bar and checklist stream in
  over SSE as each source is queried and skills get extracted, so you're not
  staring at a blank screen for a search that can take 30-90s. Brave queries
  one ATS site at a time (`brave_jobs.py`'s `DOMAIN_GROUP_SIZE = 1`) so each
  of the 15 sites gets its own row, checkmark, and live finding count as its
  query completes, rather than a batch of 5 flipping done together - this
  costs more Brave API calls than grouping would (a tradeoff made
  deliberately for the clearer progress display). Each site's own
  contribution is also capped independently (`SITE_RESULT_CAP`) rather than
  the whole search stopping the moment any one site (typically Greenhouse)
  fills the requested limit by itself, which previously meant the other 14
  sites never got queried at all. The final per-site findings count carries
  through to the results too, shown under the source breakdown.
- **Country filter** — a dropdown (defaults to United States) restricts
  results to one of 8 countries. Neither current source has a structured
  location field, so this is best-effort text matching against the posting's
  full page text *and* the search result's own title (some ATS
  pages only state location in page metadata, which shows up in the search
  engine's synthesized title but never in the scraped body) against a list of
  ~50 countries and their major cities — not just the 8 selectable ones, since
  a posting based in, say, Poland or Turkey still needs to be recognized and
  excluded when the target is US, even though it's not a pickable option —
  see `backend/app/country_filter.py`.
- **Expired-posting filtering** — pages that fetch fine (HTTP 200) but just
  say "this job has expired" / "no longer accepting applications" etc. are
  detected and dropped rather than included as a dead-link result.
- **Skill extraction mode toggle** — pick **Claude (AI)** for semantic
  extraction (understands paraphrased/implied skills, costs an Anthropic API
  call per batch of postings) or **Keyword matching (non-AI)** for a free,
  instant, fully local alternative that scans postings against a curated
  skills dictionary (`backend/app/keyword_extraction.py`). The keyword mode
  trades recall/precision for speed and zero cost — it only catches skills
  phrased close to a known variant and can't infer anything implied by the
  text, and deliberately skips ambiguous short tokens (bare "go", "r", "c",
  "spark") that would otherwise match constantly as ordinary English words.
  Every Claude-mode search feeds back into the keyword dictionary: any skill
  Claude finds that the keyword matcher doesn't already recognize gets
  persisted to `backend/data/learned_skills.json`, so keyword mode gets
  better at covering your searches over time.
- **Industries pie chart** — a pie chart next to the skills table shows what
  industries the found postings are in, classified by a keyword matcher
  against a fixed ~17-industry taxonomy (`backend/app/industry_classification.py`),
  same approximate-but-free approach as the non-AI skill extractor. Caps at 5 named slices + one folded
  "Other" wedge (more than that blurs together in a pie chart); a 1-2
  industry result renders as plain text instead of a chart, since a 2-slice
  pie doesn't tell you anything numbers don't.
- **Linked postings per skill** — click any skill in the results table to
  expand the list of postings that mentioned it, each linking to the original
  listing.
- **All postings found** — a column next to the skills table lists every
  posting analyzed, deduped and ranked by relevance to your search
  (`backend/app/relevance.py`) by default, or sortable by site posted (groups
  by the actual ATS platform — Greenhouse, Lever, etc. — not by which search
  API found it), each linking out to the original listing.

## Sources

There's no zero-configuration fallback source anymore (RemoteOK was one, but
was dropped for frequently surfacing off-relevance postings; Adzuna was
another - it had real per-country filtering and a genuine structured job
category, both lost when it was dropped). Currently only Brave Search is
active - see its entry below.

- **Google (ATS job boards)** — **disabled** in `search_service.py`'s
  `PROVIDERS` list due to a persistent account-level 403 from Google Cloud
  ("This project does not have the access to Custom Search JSON API") that
  didn't resolve even across a fresh project, fresh key, correct API
  enablement, correct key restrictions, and linked billing. The code
  (`backend/app/providers/google_jobs.py`) and setup instructions below are
  kept as-is - add `GoogleJobsProvider()` back to the `PROVIDERS` list in
  `backend/app/search_service.py` to re-enable once/if that's sorted out.
  Uses the Google Custom Search API to find postings on 15 different ATS
  platforms indexed by Google (the same "site:" search-engine trick sites
  like briansjobsearch.com use), then fetches each posting page for its full
  description. Setup:
  1. https://console.cloud.google.com/ → enable "Custom Search API" for the
     project your key belongs to, **and confirm that project has a billing
     account linked** (console.cloud.google.com/billing) — required even
     though usage stays within the free 100 queries/day tier — → create an
     API key.
  2. https://programmablesearchengine.google.com/ → create a search engine →
     under "Sites to search" add each of these URLs (whole-web search was
     discontinued for new engines in Jan 2026, so this list is exactly the
     sites the app itself restricts its query to) → copy its Search engine
     ID (cx):
     ```
     greenhouse.io/*
     jobs.lever.co/*
     recruitee.com/*
     jobs.smartrecruiters.com/*
     recruiting.paylocity.com/*
     jobs.gusto.com/*
     jobs.personio.com/*
     catsone.com/*
     trinethire.com/*
     teamtailor.com/*
     pinpointhq.com/*
     jobs.jobvite.com/*
     jobappnetwork.com/*
     breezy.hr/*
     applytojob.com/*
     ```
     `greenhouse.io` is deliberately the bare domain rather than a specific
     subdomain — Greenhouse has hosted postings at `boards.greenhouse.io`
     (legacy), `job-boards.greenhouse.io` (current default), and
     `job-boards.eu.greenhouse.io` (EU) at different times; pinning to one
     subdomain silently missed most current postings when Greenhouse
     switched defaults. The bare domain covers all of them, present and
     future.
  3. Put both in `backend/.env` as `GOOGLE_CSE_API_KEY` / `GOOGLE_CSE_ID`.

  Free tier is 100 queries/day (10 results per query), so this source caps
  itself at 50 results per search. Skipped automatically if not configured.
- **Brave Search (ATS job boards)** — currently the only active source. Same
  domain list and approach as the (disabled) Google source above -
  `backend/app/providers/ats_search_base.py` holds the shared logic;
  `google_jobs.py` and `brave_jobs.py` each just implement the search-API
  call - but via the Brave Search API instead of Google Custom Search.
  Simpler signup (no Cloud project or API-enablement
  step, and no need to separately register the site list anywhere — the
  "site:" restriction lives entirely in the query), though it still requires
  a credit card on file for identity verification (not charged within the
  $5/month free credit). Brave also caps the whole query at 400 characters
  (Google has no such limit at this length), so `brave_jobs.py` splits the
  15-domain list into 3 groups of 5 and queries each separately rather than
  sending one combined query. Setup:
  1. https://search.brave.com/api → sign up, pick the free "Search" plan.
  2. Dashboard → API Keys → create a key → put it in `backend/.env` as
     `BRAVE_SEARCH_API_KEY`.

  Only set one of the Google or Brave keys — both search the same 15
  domains, so running both just doubles API usage for no benefit (the
  resulting duplicate postings still get deduped into one either way, since
  postings found through either provider are labeled by which ATS actually
  hosts them — e.g. "Greenhouse", "Lever" — not by which search API found
  them, and dedup is by title+company, not source).

These are official/public APIs rather than scraping sites like LinkedIn or
Indeed, which prohibit scraping in their terms of service. (Arbeitnow was
dropped as a source — it's Germany/Europe-focused, which doesn't fit a
USA-first tool. RemoteOK was dropped too — its postings were frequently
off-relevance to the search query.)

### Which ATS sites are (and aren't) included, and why

briansjobsearch.com dorks against ~40 sites total. Each was checked by fetching
a real, live job posting with no JavaScript execution and confirming the
description text actually came through in the raw HTML — the same thing our
fetch step does. Only sites that passed are wired in; the rest can't work no
matter how the search engine is configured, since we never execute JS.

**Included (server-rendered, confirmed working):** Greenhouse, Lever,
Recruitee, SmartRecruiters, Paylocity, Gusto, Personio, CATS, TriNet Hire,
Teamtailor, Pinpoint, Jobvite, TalentReef (jobappnetwork.com), BreezyHR,
JazzHR (applytojob.com).

**Excluded — client-rendered JS app, returns an empty shell to a plain
fetch:** Workday, Ashby, Workable, iCIMS, ADP, Rippling, Dover, Dayforce,
Gem, Oracle Cloud/Taleo, CareerPuck.

**Excluded — consumer job-board aggregators, not a company's own ATS
postings (same category as LinkedIn/Indeed, so left out on the same ToS/
scraping-risk grounds regardless of rendering):** LinkedIn, Glassdoor,
Wellfound, BuiltIn, Y Combinator's Work at a Startup, Remote Rocketship.

**Excluded — technically impossible now:** Brian's generic wildcard
categories (`careers.*`, `jobs.*`, `people.*`, `talent.*`, and other-pages
patterns like `*/employment/*`) rely on matching arbitrary companies' own
domains across the whole web — exactly the whole-web search capability
Google discontinued for new Programmable Search Engines. A site-restricted
engine can only match domains explicitly listed in it.

**Not verified either way (inconclusive test results, left out for now):**
Factorial, Trakstar, Keka, Notion-hosted career pages.

## Setup

### Backend

```
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY (required)
.venv/bin/uvicorn app.main:app --reload
```

Runs at http://localhost:8000. `BRAVE_SEARCH_API_KEY` needs to be set or
searches will have no sources to pull from - it's currently the only active
source (see "Sources" above). `GOOGLE_CSE_API_KEY`/`GOOGLE_CSE_ID` can be set
too, but won't do anything until `GoogleJobsProvider` is added back to
`PROVIDERS` in `backend/app/search_service.py`.

### Frontend

```
cd frontend
npm install
npm run dev
```

Runs at http://localhost:5173 and talks to the backend at localhost:8000.

## How it works

1. `GET /api/search/stream` (SSE) fetches postings matching the job title and
   country from each configured source (`backend/app/providers/`), streaming
   progress events as it goes. `backend/app/dedup.py` then collapses
   duplicates by normalized (title, company) rather than URL - some job
   boards spam-repost the exact same listing under dozens of different
   URLs/IDs, which URL-based dedup alone doesn't catch and which would
   otherwise both clutter the postings list and skew skill percentages
   toward whatever one reposted listing happens to mention.
2. Depending on the extraction mode: descriptions are either batched to
   Claude (`backend/app/skill_extraction.py`), which returns a structured
   skill list per posting via tool use, or run through the local keyword
   matcher (`backend/app/keyword_extraction.py`). Both produce the same
   shape (a skill list per posting), so the rest of the pipeline doesn't
   care which one ran.
3. `backend/app/aggregator.py` counts how many postings mention each skill,
   ranks them, and keeps a link back to every posting that mentioned it.
   `backend/app/relevance.py` separately ranks all fetched postings by
   relevance to the search query for the "all postings found" list.
4. `backend/app/output_writer.py` writes the ranked report (skill rankings,
   linked postings, and the full postings list) to `backend/output/<slug>.txt`
   (and a `.json` sidecar the API/UI read back for history).
