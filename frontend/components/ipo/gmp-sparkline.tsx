import type { GMPPoint } from "@/lib/types";
import { formatPercent } from "@/lib/format";

export function GmpSparkline({ history }: { history: GMPPoint[] }) {
  const points = history
    .filter(
      (point): point is GMPPoint & { gmp_percent: number } =>
        point.gmp_percent != null,
    )
    .slice()
    .reverse();

  if (points.length < 2) {
    return (
      <p className="px-5 py-8 text-center text-sm text-muted-foreground">
        Not enough GMP observations to draw a trend yet.
      </p>
    );
  }

  const values = points.map((point) => point.gmp_percent);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const span = maximum - minimum || 1;

  const width = 640;
  const height = 140;
  const padding = 10;

  const coordinates = values.map((value, index) => {
    const x = padding + (index * (width - padding * 2)) / (values.length - 1);
    const y =
      height - padding - ((value - minimum) / span) * (height - padding * 2);
    return { x, y };
  });

  const line = coordinates
    .map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`)
    .join(" ");
  const area = [
    `M ${coordinates[0].x.toFixed(1)},${height - 1}`,
    ...coordinates.map(
      (point) => `L ${point.x.toFixed(1)},${point.y.toFixed(1)}`,
    ),
    `L ${coordinates.at(-1)!.x.toFixed(1)},${height - 1}`,
    "Z",
  ].join(" ");
  const delta = values.at(-1)! - values[0];

  return (
    <div className="space-y-2 px-5 pb-5 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {points.length} observations · latest{" "}
          <strong className="font-semibold text-foreground">
            {formatPercent(values.at(-1))}
          </strong>
        </span>
        <span>
          {formatPercent(minimum)} – {formatPercent(maximum)} range ·{" "}
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(1)} pts
        </span>
      </div>

      <svg
        viewBox={`0 0 ${width} ${height}`}
        preserveAspectRatio="none"
        role="img"
        aria-label={`GMP percentage trend from ${formatPercent(values[0])} to ${formatPercent(values.at(-1))}`}
        className="h-32 w-full"
      >
        <defs>
          <linearGradient id="gmp-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={area} fill="url(#gmp-fill)" />
        <polyline
          points={line}
          fill="none"
          stroke="var(--primary)"
          strokeWidth={2.5}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
    </div>
  );
}
