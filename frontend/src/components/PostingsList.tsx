import { useMemo, useState } from "react";
import type { PostingLink } from "../types";

interface Props {
  postings: PostingLink[];
}

type SortBy = "relevance" | "site";

export function PostingsList({ postings }: Props) {
  const [sortBy, setSortBy] = useState<SortBy>("relevance");

  const sorted = useMemo(() => {
    if (sortBy === "relevance") return postings;
    // `postings` arrives ranked by relevance; a stable sort by source keeps
    // that relevance order within each site group rather than scrambling it.
    return [...postings].sort((a, b) => a.source.localeCompare(b.source));
  }, [postings, sortBy]);

  if (postings.length === 0) {
    return <p className="empty-state">No postings found.</p>;
  }

  return (
    <div className="postings-found">
      <div className="postings-sort-control">
        <label htmlFor="postings-sort">Sort by</label>
        <select
          id="postings-sort"
          value={sortBy}
          onChange={(e) => setSortBy(e.target.value as SortBy)}
        >
          <option value="relevance">Relevance</option>
          <option value="site">Site posted</option>
        </select>
      </div>
      <ol className="postings-found-list">
        {sorted.map((posting, i) => (
          <li key={posting.url ?? `${posting.source}-${i}`}>
            <span className="posting-rank">{i + 1}</span>
            <span className="posting-info">
              {posting.url ? (
                <a href={posting.url} target="_blank" rel="noopener noreferrer">
                  {posting.title}
                </a>
              ) : (
                <span>{posting.title}</span>
              )}
              {posting.company && <span className="posting-company"> @ {posting.company}</span>}
              <span className="posting-source"> · {posting.source}</span>
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
