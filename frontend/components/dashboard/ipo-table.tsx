import Link from "next/link";

import { Badge, gmpTone, statusTone, verdictTone } from "@/components/ui/badge";
import type { IpoSortField } from "@/lib/api";
import { dashboardHref, type DashboardQuery } from "@/lib/dashboard-query";
import {
  formatDate,
  formatIssueSize,
  formatMultiple,
  formatPercent,
  formatPriceBand,
  formatText,
} from "@/lib/format";
import type { IPOSummary } from "@/lib/types";

function boardLabel(category: string | null): string {
  return category?.toUpperCase() === "SME" ? "SME" : "Mainboard";
}

function GmpBadge({ ipo, floor }: { ipo: IPOSummary; floor: number }) {
  const meets = ipo.gmp_percent != null && ipo.gmp_percent >= floor;
  return (
    <div className="flex flex-col items-start gap-1">
      <Badge tone={gmpTone(ipo.gmp_percent)}>
        {formatPercent(ipo.gmp_percent)}
        {ipo.gmp_percent_derived ? "*" : ""}
      </Badge>
      <span className="text-[11px] text-muted-foreground">
        {ipo.gmp != null ? `₹${ipo.gmp}` : "—"}
        {meets ? " · meets screen" : ""}
      </span>
    </div>
  );
}

export function ResearchBadge({ ipo }: { ipo: IPOSummary }) {
  switch (ipo.research_status) {
    case "done":
      return ipo.research_verdict ? (
        <Badge tone={verdictTone(ipo.research_verdict)}>
          AI · {ipo.research_verdict}
        </Badge>
      ) : (
        <Badge tone="info">AI done</Badge>
      );
    case "queued":
    case "running":
      return <Badge tone="info">AI running…</Badge>;
    case "failed":
      return ipo.research_verdict ? (
        <Badge tone={verdictTone(ipo.research_verdict)}>
          AI · {ipo.research_verdict}
        </Badge>
      ) : (
        <Badge tone="danger">AI failed</Badge>
      );
    default:
      return <span className="text-xs text-muted-foreground">Not run</span>;
  }
}

function SortableHeader({
  field,
  label,
  query,
}: {
  field: IpoSortField;
  label: string;
  query: DashboardQuery;
}) {
  const isActive = query.sort === field;
  const firstOrder = field === "name" || field === "close_date" ? "asc" : "desc";
  const nextOrder = isActive
    ? query.order === "asc"
      ? "desc"
      : "asc"
    : firstOrder;

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
        href={dashboardHref(query, { sort: field, order: nextOrder })}
        scroll={false}
        className="inline-flex items-center gap-1 hover:text-foreground"
      >
        {label}
        <span
          aria-hidden="true"
          className={isActive ? "text-primary" : "text-muted-foreground/50"}
        >
          {isActive ? (query.order === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </Link>
    </th>
  );
}

function MobileCard({ ipo, floor }: { ipo: IPOSummary; floor: number }) {
  return (
    <li>
      <Link
        href={`/ipos/${ipo.id}`}
        className="block space-y-3 px-4 py-4 transition-colors hover:bg-muted/40"
      >
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="truncate font-medium">{ipo.name}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {[boardLabel(ipo.category), ipo.sector, ipo.exchange]
                .filter(Boolean)
                .join(" · ")}
            </p>
          </div>
          <GmpBadge ipo={ipo} floor={floor} />
        </div>
        <dl className="grid grid-cols-3 gap-2 text-xs">
          <div>
            <dt className="text-muted-foreground">Price</dt>
            <dd className="font-medium">
              {formatPriceBand(
                ipo.issue_price_lower,
                ipo.issue_price_upper,
                ipo.issue_price,
              )}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Subscribed</dt>
            <dd className="font-medium">{formatMultiple(ipo.subscription)}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Closes</dt>
            <dd className="font-medium">{formatDate(ipo.close_date)}</dd>
          </div>
        </dl>
        <div className="flex flex-wrap items-center gap-2">
          {ipo.status ? (
            <Badge tone={statusTone(ipo.status)}>
              <span className="capitalize">{ipo.status}</span>
            </Badge>
          ) : null}
          <ResearchBadge ipo={ipo} />
        </div>
      </Link>
    </li>
  );
}

export function IpoTable({
  items,
  query,
  floor,
}: {
  items: IPOSummary[];
  query: DashboardQuery;
  floor: number;
}) {
  return (
    <>
      <ul className="divide-y divide-border md:hidden">
        {items.map((ipo) => (
          <MobileCard key={ipo.id} ipo={ipo} floor={floor} />
        ))}
      </ul>

      <div className="hidden overflow-x-auto md:block">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/50 text-[11px] uppercase tracking-wide text-muted-foreground">
              <SortableHeader field="name" label="Company" query={query} />
              <SortableHeader field="gmp_percent" label="Latest GMP" query={query} />
              <SortableHeader field="issue_price" label="Price band" query={query} />
              <SortableHeader field="subscription" label="Subscribed" query={query} />
              <SortableHeader field="close_date" label="Closes" query={query} />
              <th scope="col" className="px-3 py-3 font-medium">
                AI research
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {items.map((ipo) => (
              <tr key={ipo.id} className="align-top transition-colors hover:bg-muted/40">
                <td className="px-3 py-3">
                  <Link
                    href={`/ipos/${ipo.id}`}
                    className="font-medium text-foreground underline-offset-4 hover:text-primary hover:underline"
                  >
                    {ipo.name}
                  </Link>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground">
                    <Badge tone={ipo.category?.toUpperCase() === "SME" ? "info" : "primary"}>
                      {boardLabel(ipo.category)}
                    </Badge>
                    {ipo.status ? (
                      <Badge tone={statusTone(ipo.status)}>
                        <span className="capitalize">{ipo.status}</span>
                      </Badge>
                    ) : null}
                    <span>
                      {[ipo.sector, ipo.exchange].filter(Boolean).join(" · ") ||
                        formatText(null)}
                    </span>
                  </div>
                </td>
                <td className="px-3 py-3">
                  <GmpBadge ipo={ipo} floor={floor} />
                </td>
                <td className="px-3 py-3 whitespace-nowrap">
                  {formatPriceBand(
                    ipo.issue_price_lower,
                    ipo.issue_price_upper,
                    ipo.issue_price,
                  )}
                  <p className="text-[11px] text-muted-foreground">
                    {ipo.ipo_size_cr ? formatIssueSize(ipo.ipo_size_cr) : "Size —"}
                  </p>
                </td>
                <td className="px-3 py-3">{formatMultiple(ipo.subscription)}</td>
                <td className="px-3 py-3 whitespace-nowrap">
                  {formatDate(ipo.close_date)}
                </td>
                <td className="px-3 py-3">
                  <ResearchBadge ipo={ipo} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
