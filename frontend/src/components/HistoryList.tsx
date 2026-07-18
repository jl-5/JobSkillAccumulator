import type { HistoryEntry } from "../types";

interface Props {
  entries: HistoryEntry[];
  activeSlug: string | null;
  onSelect: (slug: string) => void;
}

export function HistoryList({ entries, activeSlug, onSelect }: Props) {
  if (entries.length === 0) {
    return <p className="empty-state">No past searches yet.</p>;
  }

  return (
    <ul className="history-list">
      {entries.map((entry) => (
        <li key={entry.slug}>
          <button
            type="button"
            className={entry.slug === activeSlug ? "history-item active" : "history-item"}
            onClick={() => onSelect(entry.slug)}
          >
            <span className="history-item-title">{entry.job_title}</span>
            <span className="history-item-meta">
              {new Date(entry.generated_at).toLocaleString()} · {entry.postings_analyzed} postings ·{" "}
              {entry.country.toUpperCase()} · {entry.extraction_mode === "claude" ? "AI" : "keyword"}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
