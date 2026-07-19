export interface PostingLink {
  title: string;
  company: string | null;
  source: string;
  url: string | null;
}

export interface SkillCount {
  skill: string;
  count: number;
  percentage: number;
  postings: PostingLink[];
}

export interface IndustryCount {
  industry: string;
  count: number;
  percentage: number;
}

export type ExtractionMode = "claude" | "keyword";

export interface SearchResult {
  slug: string;
  job_title: string;
  country: string;
  extraction_mode: ExtractionMode;
  site_result_cap: number;
  exclude_defense: boolean;
  generated_at: string;
  postings_analyzed: number;
  source_breakdown: Record<string, string>;
  site_breakdown: Record<string, number>;
  skills: SkillCount[];
  industries: IndustryCount[];
  postings: PostingLink[];
  txt_path: string;
  json_path: string;
}

export interface HistoryEntry {
  slug: string;
  job_title: string;
  country: string;
  extraction_mode: ExtractionMode;
  site_result_cap: number;
  exclude_defense: boolean;
  generated_at: string;
  postings_analyzed: number;
}

/** code -> display name, e.g. { us: "United States" } */
export type CountryOptions = Record<string, string>;

export type SourceStatus = "pending" | "checking" | "done";

export interface SiteProgress {
  name: string;
  status: SourceStatus;
  count?: number;
}

export interface SourceProgress {
  name: string;
  status: SourceStatus;
  detail?: string;
  /** Individual ATS sites this source checks, if it breaks its search down
   * that way (e.g. Brave queries one site at a time) - each gets its own
   * checkmark as it completes, instead of the whole source flipping done
   * as a unit. */
  sites?: SiteProgress[];
}

export interface SearchProgressState {
  phase: "fetching" | "extracting" | "done";
  sources: SourceProgress[];
  extracting?: { completed: number; total: number };
}

export type SearchStreamEvent =
  | { type: "start"; sources: string[] }
  | { type: "provider_start"; source: string }
  | { type: "provider_progress"; source: string; detail: string }
  | { type: "provider_sites"; source: string; sites: string[] }
  | { type: "site_start"; source: string; site: string }
  | { type: "site_done"; source: string; site: string; count: number }
  | { type: "provider_done"; source: string; status: string }
  | { type: "extracting_start"; postings: number; total_batches: number }
  | { type: "extracting_progress"; completed: number; total: number }
  | { type: "learned_skills"; count: number }
  | { type: "result"; result: SearchResult }
  | { type: "error"; message: string };
