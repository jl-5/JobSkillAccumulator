import type { IndustryCount } from "../types";

interface Props {
  industries: IndustryCount[];
}

// Dataviz guidance: pie/donut is "part-to-whole at a glance only, <= 6
// segments" - past that, adjacent slices blur together. Cap at 5 named
// industries + one folded "Other" slice rather than showing every category
// the backend's taxonomy can produce.
const MAX_NAMED_SLICES = 5;
const OTHER_LABEL = "Other";
const SERIES_VARS = ["--series-1", "--series-2", "--series-3", "--series-4", "--series-5"];
// Thin surface-color gap between wedges instead of a border, same spacing
// rule as adjacent bars/stacked segments elsewhere in this app.
const GAP_DEGREES = 1.5;

interface Slice {
  label: string;
  count: number;
  percentage: number;
  color: string;
}

function buildSlices(industries: IndustryCount[]): Slice[] {
  const total = industries.reduce((sum, i) => sum + i.count, 0);
  if (total === 0) return [];

  const named = industries.filter((i) => i.industry !== OTHER_LABEL);
  const backendOtherCount = industries.find((i) => i.industry === OTHER_LABEL)?.count ?? 0;

  const top = named.slice(0, MAX_NAMED_SLICES);
  const overflowCount =
    named.slice(MAX_NAMED_SLICES).reduce((sum, i) => sum + i.count, 0) + backendOtherCount;

  const slices: Slice[] = top.map((industry, i) => ({
    label: industry.industry,
    count: industry.count,
    percentage: Math.round((industry.count / total) * 1000) / 10,
    color: `var(${SERIES_VARS[i]})`,
  }));

  if (overflowCount > 0) {
    slices.push({
      label: OTHER_LABEL,
      count: overflowCount,
      percentage: Math.round((overflowCount / total) * 1000) / 10,
      color: "var(--text-muted)",
    });
  }

  return slices;
}

function polarPoint(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180;
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
}

function wedgePath(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const start = polarPoint(cx, cy, r, endAngle);
  const end = polarPoint(cx, cy, r, startAngle);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y} Z`;
}

export function IndustryPieChart({ industries }: Props) {
  const slices = buildSlices(industries);

  if (slices.length === 0) {
    return null;
  }

  // Anti-pattern: a 1-2 slice pie reads better as plain numbers than a chart.
  if (slices.length < 3) {
    const total = slices.reduce((sum, s) => sum + s.count, 0);
    return (
      <div className="industry-summary">
        {slices.map((s) => (
          <p key={s.label}>
            <strong>{s.percentage}%</strong> of postings are in <strong>{s.label}</strong> ({s.count} of{" "}
            {total})
          </p>
        ))}
      </div>
    );
  }

  let cursor = 0;
  const cx = 100;
  const cy = 100;
  const r = 90;

  return (
    <div className="industry-pie">
      <svg viewBox="0 0 200 200" role="img" aria-label="Industry breakdown of postings found">
        {slices.map((slice) => {
          const sweep = (slice.percentage / 100) * 360;
          const startAngle = cursor + GAP_DEGREES / 2;
          const endAngle = cursor + sweep - GAP_DEGREES / 2;
          cursor += sweep;
          if (endAngle <= startAngle) return null;
          return (
            <path key={slice.label} d={wedgePath(cx, cy, r, startAngle, endAngle)} fill={slice.color}>
              <title>
                {slice.label}: {slice.count} postings ({slice.percentage}%)
              </title>
            </path>
          );
        })}
      </svg>

      <ul className="industry-legend">
        {slices.map((slice) => (
          <li key={slice.label}>
            <span className="industry-swatch" style={{ background: slice.color }} />
            <span className="industry-legend-label">{slice.label}</span>
            <span className="industry-legend-value">{slice.percentage}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
