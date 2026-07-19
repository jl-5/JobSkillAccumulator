import { useState } from "react";
import type { FormEvent } from "react";
import type { CountryOptions, ExtractionMode } from "../types";

const MAX_SITE_RESULT_CAP = 50;

interface Props {
  onSearch: (jobTitle: string) => void;
  loading: boolean;
  countries: CountryOptions;
  country: string;
  onCountryChange: (country: string) => void;
  extractionMode: ExtractionMode;
  onExtractionModeChange: (mode: ExtractionMode) => void;
  siteResultCap: number;
  onSiteResultCapChange: (cap: number) => void;
  excludeDefense: boolean;
  onExcludeDefenseChange: (exclude: boolean) => void;
}

export function SearchForm({
  onSearch,
  loading,
  countries,
  country,
  onCountryChange,
  extractionMode,
  onExtractionModeChange,
  siteResultCap,
  onSiteResultCapChange,
  excludeDefense,
  onExcludeDefenseChange,
}: Props) {
  const [jobTitle, setJobTitle] = useState("");

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = jobTitle.trim();
    if (trimmed) onSearch(trimmed);
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <input
        type="text"
        placeholder="e.g. Senior Backend Engineer"
        value={jobTitle}
        onChange={(e) => setJobTitle(e.target.value)}
        disabled={loading}
      />
      <select
        className="country-select"
        value={country}
        onChange={(e) => onCountryChange(e.target.value)}
        disabled={loading}
        aria-label="Country"
      >
        {Object.entries(countries).map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
      <select
        className="extraction-mode-select"
        value={extractionMode}
        onChange={(e) => onExtractionModeChange(e.target.value as ExtractionMode)}
        disabled={loading}
        aria-label="Skill extraction method"
      >
        <option value="claude">Claude (AI)</option>
        <option value="keyword">Keyword matching (non-AI)</option>
      </select>
      <label className="site-cap-label">
        Max results per site
        <input
          type="number"
          className="site-cap-input"
          min={1}
          max={MAX_SITE_RESULT_CAP}
          value={siteResultCap}
          onChange={(e) => {
            const value = Number(e.target.value);
            if (Number.isNaN(value)) return;
            onSiteResultCapChange(Math.min(MAX_SITE_RESULT_CAP, Math.max(1, value)));
          }}
          disabled={loading}
          aria-label="Max results per site"
        />
      </label>
      <label className="exclude-defense-label">
        <input
          type="checkbox"
          checked={excludeDefense}
          onChange={(e) => onExcludeDefenseChange(e.target.checked)}
          disabled={loading}
        />
        Exclude defense/clearance jobs
      </label>
      <button type="submit" disabled={loading || !jobTitle.trim()}>
        {loading ? "Searching…" : "Search"}
      </button>
    </form>
  );
}
