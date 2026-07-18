import { useEffect, useRef, useState } from "react";
import { getCountries, getHistory, getHistoryDetail, searchStream } from "./api";
import { HistoryList } from "./components/HistoryList";
import { IndustryPieChart } from "./components/IndustryPieChart";
import { PostingsList } from "./components/PostingsList";
import { SearchForm } from "./components/SearchForm";
import { SearchProgress } from "./components/SearchProgress";
import { SkillsTable } from "./components/SkillsTable";
import { SourceBreakdown } from "./components/SourceBreakdown";
import type {
  CountryOptions,
  ExtractionMode,
  HistoryEntry,
  SearchProgressState,
  SearchResult,
  SearchStreamEvent,
} from "./types";
import "./App.css";

function App() {
  const [result, setResult] = useState<SearchResult | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [countries, setCountries] = useState<CountryOptions>({ us: "United States" });
  const [country, setCountry] = useState("us");
  const [extractionMode, setExtractionMode] = useState<ExtractionMode>("claude");
  const [siteResultCap, setSiteResultCap] = useState(10);
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState<SearchProgressState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  function refreshHistory() {
    getHistory().then(setHistory).catch(() => setHistory([]));
  }

  useEffect(() => {
    refreshHistory();
    getCountries()
      .then(setCountries)
      .catch(() => {});
    return () => cleanupRef.current?.();
  }, []);

  function handleStreamEvent(event: SearchStreamEvent) {
    if (event.type === "result") {
      setResult(event.result);
      setProgress(null);
      setLoading(false);
      refreshHistory();
      return;
    }
    if (event.type === "error") {
      setError(event.message);
      setProgress(null);
      setLoading(false);
      return;
    }

    setProgress((prev) => {
      if (event.type === "start") {
        return {
          phase: "fetching",
          sources: event.sources.map((name) => ({ name, status: "pending" as const })),
        };
      }
      if (!prev) return prev;
      switch (event.type) {
        case "provider_start":
          return {
            ...prev,
            sources: prev.sources.map((s) =>
              s.name === event.source ? { ...s, status: "checking" as const } : s,
            ),
          };
        case "provider_progress":
          return {
            ...prev,
            sources: prev.sources.map((s) =>
              s.name === event.source ? { ...s, detail: event.detail } : s,
            ),
          };
        case "provider_sites":
          return {
            ...prev,
            sources: prev.sources.map((s) =>
              s.name === event.source
                ? { ...s, sites: event.sites.map((name) => ({ name, status: "pending" as const })) }
                : s,
            ),
          };
        case "site_start":
          return {
            ...prev,
            sources: prev.sources.map((s) =>
              s.name === event.source
                ? {
                    ...s,
                    sites: s.sites?.map((site) =>
                      site.name === event.site ? { ...site, status: "checking" as const } : site,
                    ),
                  }
                : s,
            ),
          };
        case "site_done":
          return {
            ...prev,
            sources: prev.sources.map((s) =>
              s.name === event.source
                ? {
                    ...s,
                    sites: s.sites?.map((site) =>
                      site.name === event.site
                        ? { ...site, status: "done" as const, count: event.count }
                        : site,
                    ),
                  }
                : s,
            ),
          };
        case "provider_done":
          return {
            ...prev,
            sources: prev.sources.map((s) =>
              s.name === event.source ? { ...s, status: "done" as const, detail: event.status } : s,
            ),
          };
        case "extracting_start":
          return { ...prev, phase: "extracting", extracting: { completed: 0, total: event.total_batches } };
        case "extracting_progress":
          return { ...prev, extracting: { completed: event.completed, total: event.total } };
        default:
          return prev;
      }
    });
  }

  function handleSearch(jobTitle: string) {
    cleanupRef.current?.();
    setLoading(true);
    setError(null);
    setProgress(null);
    cleanupRef.current = searchStream(
      jobTitle,
      country,
      extractionMode,
      siteResultCap,
      handleStreamEvent,
      () => {
        setError("Lost connection to the server");
        setProgress(null);
        setLoading(false);
      },
    );
  }

  async function handleSelectHistory(slug: string) {
    cleanupRef.current?.();
    setLoading(false);
    setProgress(null);
    setError(null);
    try {
      const detail = await getHistoryDetail(slug);
      setResult(detail);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load search");
    }
  }

  return (
    <div className="layout">
      <aside className="sidebar">
        <h2>Past Searches</h2>
        <HistoryList entries={history} activeSlug={result?.slug ?? null} onSelect={handleSelectHistory} />
      </aside>

      <main className="main">
        <h1>Job Skill Accumulator</h1>
        <p className="subtitle">
          Enter a job title or keywords to see the most commonly requested skills across current
          postings.
        </p>

        <SearchForm
          onSearch={handleSearch}
          loading={loading}
          countries={countries}
          country={country}
          onCountryChange={setCountry}
          extractionMode={extractionMode}
          onExtractionModeChange={setExtractionMode}
          siteResultCap={siteResultCap}
          onSiteResultCapChange={setSiteResultCap}
        />

        {loading && progress && <SearchProgress progress={progress} />}

        {error && <p className="error-banner">{error}</p>}

        {!loading && result && (
          <section className="results">
            <h2>{result.job_title}</h2>
            <SourceBreakdown
              sourceBreakdown={result.source_breakdown}
              siteBreakdown={result.site_breakdown}
              postingsAnalyzed={result.postings_analyzed}
            />
            <p className="saved-note">
              Saved to {result.txt_path} · Skill extraction:{" "}
              {result.extraction_mode === "claude" ? "Claude (AI)" : "Keyword matching (non-AI)"} ·
              Max results per site: {result.site_result_cap}
            </p>

            <section className="industries-section">
              <h3>Industries</h3>
              <IndustryPieChart industries={result.industries} />
            </section>

            <div className="results-columns">
              <div className="results-skills-column">
                <SkillsTable skills={result.skills} />
              </div>
              <div className="results-postings-column">
                <h3>All postings found ({result.postings.length})</h3>
                <PostingsList postings={result.postings} />
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  );
}

export default App;
