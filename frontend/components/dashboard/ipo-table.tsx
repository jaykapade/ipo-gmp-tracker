import Link from "next/link";

import { Badge, gmpTone, statusTone } from "@/components/ui/badge";
import type { IpoSortField } from "@/lib/api";
import {
  formatCurrency,
  formatDate,
  formatMultiple,
  formatPercent,
  formatPriceBand,
  formatText,
} from "@/lib/format";
import type { IPOSummary } from "@/lib/types";

import type { DashboardQuery } from "./ipo-filters";

function GmpCell({ ipo }: { ipo: IPOSummary }) {
  return (
    <div className="space-y-1">
      <Badge tone={gmpTone(ipo.gmp_percent)}>
        {formatPercent(ipo.gmp_percent)}
        {ipo.gmp_percent_derived ? " (derived)" : ""}
      </Badge>
      <p className="text-[11px] text-muted-foreground">
        {formatCurrency(ipo.gmp)}
        {ipo.latest_gmp_source ? ` · ${ipo.latest_gmp_source}` : ""}
      </p>
    </div>
  );
}

function sortHref(field: IpoSortField, query: DashboardQuery): string {
  const params = new URLSearchParams();
  params.set("min_gmp", String(query.minGmp));
  if (query.status) params.set("status", query.status);
  if (query.q?.trim()) params.set("q", query.q.trim());

  // Numeric/date columns are most useful highest/newest first on first click.
  const firstOrder = field === "name" ? "asc" : "desc";
  const nextOrder =
    query.sort === field
      ? query.order === "asc"
        ? "desc"
        : "asc"
      : firstOrder;

  params.set("sort", field);
  params.set("order", nextOrder);

  return `/?${params.toString()}`;
}

function SortableHeader({
  field,
  label,
  query,
  align = "left",
}: {
  field: IpoSortField;
  label: string;
  query: DashboardQuery;
  align?: "left" | "right";
}) {
  const isActive = query.sort === field;
  const indicator = isActive ? (query.order === "asc" ? "↑" : "↓") : "↕";

  return (
    <th
      scope="col"
      aria-sort={
        isActive
          ? query.order === "asc"
            ? "ascending"
            : "descending"
          : "none"
      }
      className="px-3 py-3 font-medium"
    >
      <Link
        href={sortHref(field, query)}
        className={
          align === "right"
            ? "flex items-center justify-end gap-1 hover:text-foreground"
            : "flex items-center gap-1 hover:text-foreground"
        }
      >
        {label}
        <span
          aria-hidden="true"
          className={isActive ? "text-primary" : "text-muted-foreground/60"}
        >
          {indicator}
        </span>
      </Link>
    </th>
  );
}

export function IpoTable({
  items,
  query,
}: {
  items: IPOSummary[];
  query: DashboardQuery;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[860px] text-left text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50 text-[11px] uppercase tracking-wide text-muted-foreground">
            <SortableHeader field="name" label="Company" query={query} />
            <th scope="col" className="px-3 py-3 font-medium">
              Status
            </th>
            <SortableHeader
              field="gmp_percent"
              label="Latest GMP"
              query={query}
            />
            <SortableHeader
              field="issue_price"
              label="Issue price"
              query={query}
            />
            <th scope="col" className="px-3 py-3 font-medium">
              Size
            </th>
            <SortableHeader
              field="subscription"
              label="Subscribed"
              query={query}
            />
            <SortableHeader field="close_date" label="Closes" query={query} />
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {items.map((ipo) => (
            <tr key={ipo.id} className="align-top hover:bg-muted/40">
              <td className="px-5 py-3">
                <Link
                  href={`/ipos/${ipo.id}`}
                  className="font-medium text-foreground underline-offset-4 hover:text-primary hover:underline"
                >
                  {ipo.name}
                </Link>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {[ipo.category, ipo.sector, ipo.exchange]
                    .filter(Boolean)
                    .join(" · ") || "—"}
                </p>
              </td>
              <td className="px-3 py-3">
                <Badge tone={statusTone(ipo.status)}>
                  {formatText(ipo.status)}
                </Badge>
              </td>
              <td className="px-3 py-3">
                <GmpCell ipo={ipo} />
              </td>
              <td className="px-3 py-3">
                {formatPriceBand(
                  ipo.issue_price_lower,
                  ipo.issue_price_upper,
                  ipo.issue_price,
                )}
              </td>
              <td className="px-3 py-3 text-muted-foreground">
                {ipo.ipo_size_cr ? `₹${ipo.ipo_size_cr} cr` : "—"}
              </td>
              <td className="px-3 py-3">
                {formatMultiple(ipo.subscription)}
              </td>
              <td className="px-3 py-3">{formatDate(ipo.close_date)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
