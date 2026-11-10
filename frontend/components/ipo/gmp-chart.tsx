"use client";

import {
  Area,
  AreaChart,
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  formatChartDate,
  formatCurrency,
  formatDateTime,
  formatPercent,
} from "@/lib/format";
import type { GMPPoint } from "@/lib/types";

interface ChartPoint {
  label: string;
  percent: number;
  gmp: number | null;
  source: string;
  recordedAt: string;
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload?: ChartPoint }>;
}) {
  const point = active ? payload?.[0]?.payload : undefined;
  if (!point) return null;

  return (
    <div className="rounded-lg border border-border bg-card px-3 py-2 text-xs shadow-md">
      <p className="font-medium">{point.recordedAt}</p>
      <p className="mt-1 text-sm font-semibold">
        {formatPercent(point.percent)}
        <span className="ml-2 font-normal text-muted-foreground">
          {formatCurrency(point.gmp)}
        </span>
      </p>
      <p className="mt-0.5 text-muted-foreground">{point.source}</p>
    </div>
  );
}

export function GmpChart({ history }: { history: GMPPoint[] }) {
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

  const data: ChartPoint[] = points.map((point) => ({
    label: formatChartDate(point.recorded_at),
    percent: Number(point.gmp_percent.toFixed(2)),
    gmp: point.gmp,
    source: point.source,
    recordedAt: formatDateTime(point.recorded_at),
  }));

  const values = data.map((point) => point.percent);
  const minimum = Math.min(...values);
  const maximum = Math.max(...values);
  const first = data[0];
  const latest = data[data.length - 1];
  const delta = latest.percent - first.percent;
  const yMin = Math.min(0, Math.floor(minimum - 5));
  const yMax = Math.max(25, Math.ceil(maximum + 5));

  return (
    <div className="space-y-3 px-5 pb-5 pt-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {data.length} observations · latest{" "}
          <strong className="font-semibold text-foreground">
            {formatPercent(latest.percent)}
          </strong>
        </span>
        <span>
          {formatPercent(minimum)} – {formatPercent(maximum)} range ·{" "}
          {delta >= 0 ? "+" : ""}
          {delta.toFixed(1)} pts
        </span>
      </div>

      <div className="h-56 w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="gmp-fill" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="var(--primary)"
                  stopOpacity={0.3}
                />
                <stop
                  offset="100%"
                  stopColor="var(--primary)"
                  stopOpacity={0.02}
                />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="var(--border)"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              minTickGap={24}
              tickMargin={8}
            />
            <YAxis
              domain={[yMin, yMax]}
              tickFormatter={(value: number) => `${value}%`}
              tickLine={false}
              axisLine={false}
              tick={{ fill: "var(--muted-foreground)", fontSize: 11 }}
              width={48}
            />

            <ReferenceLine
              y={20}
              stroke="var(--warning)"
              strokeDasharray="4 4"
              label={{
                value: "20% screen",
                position: "insideTopRight",
                fill: "var(--warning)",
                fontSize: 10,
              }}
            />

            <Tooltip
              content={<ChartTooltip />}
              cursor={{
                stroke: "var(--muted-foreground)",
                strokeDasharray: "3 3",
              }}
            />

            <Area
              type="monotone"
              dataKey="percent"
              name="GMP"
              stroke="var(--primary)"
              strokeWidth={2}
              fill="url(#gmp-fill)"
              dot={false}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
