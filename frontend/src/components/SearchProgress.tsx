import type { SearchProgressState, SiteProgress, SourceProgress } from "../types";

interface Props {
  progress: SearchProgressState;
}

const FETCH_WEIGHT = 40;
const EXTRACT_WEIGHT = 60;

/** Flattens each source into its individual sites when it has them, or
 * treats the source itself as a single step otherwise - used for both
 * progress-percent math and rendering, so the two always agree on what
 * counts as "a step". */
function steps(sources: SourceProgress[]): { status: SourceProgress["status"] }[] {
  return sources.flatMap((s) => (s.sites && s.sites.length > 0 ? s.sites : [s]));
}

function computePercent(progress: SearchProgressState): number {
  const allSteps = steps(progress.sources);
  const done = allSteps.filter((s) => s.status === "done").length;
  const fetchPercent = allSteps.length === 0 ? 0 : (done / allSteps.length) * FETCH_WEIGHT;

  if (progress.phase === "fetching") {
    return fetchPercent;
  }

  const extractPercent = progress.extracting
    ? (progress.extracting.completed / progress.extracting.total) * EXTRACT_WEIGHT
    : 0;

  if (progress.phase === "done") {
    return 100;
  }

  return FETCH_WEIGHT + extractPercent;
}

function statusIcon(status: SiteProgress["status"]): string {
  if (status === "checking") return "●";
  if (status === "done") return "✓";
  return "·";
}

export function SearchProgress({ progress }: Props) {
  const percent = Math.min(100, Math.round(computePercent(progress)));

  return (
    <div className="search-progress">
      <div className="search-progress-bar-track">
        <div className="search-progress-bar-fill" style={{ width: `${percent}%` }} />
      </div>
      <div className="search-progress-label">{percent}%</div>

      <ul className="search-progress-sources">
        {progress.sources.flatMap((source) => {
          // A source that breaks itself down into individual sites (e.g.
          // Brave queries one ATS site at a time) is shown as its sites
          // directly, each with its own checkmark - not as one row for the
          // whole source, which would hide exactly the detail being tracked.
          if (source.sites && source.sites.length > 0) {
            return source.sites.map((site) => (
              <li key={`${source.name}:${site.name}`} className={`source-status source-status-${site.status}`}>
                <span className="source-status-icon">{statusIcon(site.status)}</span>
                <span className="source-status-name">{site.name}</span>
                {site.count !== undefined && (
                  <span className="source-status-detail">
                    {site.count} {site.count === 1 ? "finding" : "findings"}
                  </span>
                )}
              </li>
            ));
          }

          return (
            <li key={source.name} className={`source-status source-status-${source.status}`}>
              <span className="source-status-icon">{statusIcon(source.status)}</span>
              <span className="source-status-name">{source.name}</span>
              {source.detail && <span className="source-status-detail">{source.detail}</span>}
            </li>
          );
        })}
      </ul>

      {progress.extracting && (
        <p className="search-progress-extracting">
          Extracting skills with Claude… ({progress.extracting.completed}/{progress.extracting.total} batches)
        </p>
      )}
    </div>
  );
}
