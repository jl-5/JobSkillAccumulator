import type {
  CountryOptions,
  ExtractionMode,
  HistoryEntry,
  SearchResult,
  SearchStreamEvent,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function handle<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? `Request failed with status ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getCountries(): Promise<CountryOptions> {
  return fetch(`${API_BASE}/api/countries`).then((r) => handle<CountryOptions>(r));
}

export function getHistory(): Promise<HistoryEntry[]> {
  return fetch(`${API_BASE}/api/history`).then((r) => handle<HistoryEntry[]>(r));
}

export function getHistoryDetail(slug: string): Promise<SearchResult> {
  return fetch(`${API_BASE}/api/history/${slug}`).then((r) => handle<SearchResult>(r));
}

/** Opens the live-progress search stream. Returns a cleanup function to close it early. */
export function searchStream(
  jobTitle: string,
  country: string,
  extractionMode: ExtractionMode,
  siteResultCap: number,
  onEvent: (event: SearchStreamEvent) => void,
  onConnectionError: () => void,
): () => void {
  const params = new URLSearchParams({
    job_title: jobTitle,
    country,
    extraction_mode: extractionMode,
    site_result_cap: String(siteResultCap),
  });
  const url = `${API_BASE}/api/search/stream?${params.toString()}`;
  const source = new EventSource(url);

  source.onmessage = (e) => {
    const data = JSON.parse(e.data) as SearchStreamEvent;
    onEvent(data);
    if (data.type === "result" || data.type === "error") {
      source.close();
    }
  };

  source.onerror = () => {
    onConnectionError();
    source.close();
  };

  return () => source.close();
}
