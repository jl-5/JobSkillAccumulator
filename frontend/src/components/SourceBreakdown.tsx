interface Props {
  sourceBreakdown: Record<string, string>;
  siteBreakdown: Record<string, number>;
  postingsAnalyzed: number;
}

export function SourceBreakdown({ sourceBreakdown, siteBreakdown, postingsAnalyzed }: Props) {
  const sites = Object.entries(siteBreakdown).sort(([aName, aCount], [bName, bCount]) => {
    if (bCount !== aCount) return bCount - aCount;
    return aName.localeCompare(bName);
  });

  return (
    <div className="source-breakdown">
      <span className="source-breakdown-total">{postingsAnalyzed} postings analyzed</span>
      <ul>
        {Object.entries(sourceBreakdown).map(([source, status]) => (
          <li key={source}>
            <strong>{source}:</strong> {status}
          </li>
        ))}
      </ul>

      {sites.length > 0 && (
        <ul className="site-breakdown-list">
          {sites.map(([site, count]) => (
            <li key={site}>
              {site}: <strong>{count}</strong>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
