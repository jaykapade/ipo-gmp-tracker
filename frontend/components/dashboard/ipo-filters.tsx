import Link from "next/link";

import type { IpoSortField } from "@/lib/api";

const STATUS_OPTIONS = ["Open", "Upcoming", "Closed", "Listed"] as const;

export interface DashboardQuery {
  minGmp: number;
  status?: string;
  q?: string;
  sort: IpoSortField;
  order: "asc" | "desc";
}

export function IpoFilters({ query }: { query: DashboardQuery }) {
  return (
    <form
      method="get"
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm sm:flex-row sm:flex-wrap sm:items-end"
    >
      <input type="hidden" name="sort" value={query.sort} />
      <input type="hidden" name="order" value={query.order} />

      <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
        Search company
        <input
          type="search"
          name="q"
          defaultValue={query.q}
          maxLength={100}
          placeholder="e.g. Sunrise"
          className="h-9 w-full min-w-44 rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/70 sm:w-48"
        />
      </label>

      <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
        Minimum GMP %
        <input
          type="number"
          name="min_gmp"
          defaultValue={query.minGmp}
          min={0}
          max={1000}
          step={1}
          className="h-9 w-32 rounded-md border border-border bg-background px-3 text-sm text-foreground"
        />
      </label>

      <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
        Status
        <select
          name="status"
          defaultValue={query.status ?? ""}
          className="h-9 min-w-36 rounded-md border border-border bg-background px-3 text-sm text-foreground"
        >
          <option value="">All statuses</option>
          {STATUS_OPTIONS.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>

      <div className="flex items-center gap-2 sm:ml-auto">
        <button
          type="submit"
          className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          Apply filters
        </button>
        <Link
          href="/"
          className="h-9 rounded-md border border-border px-4 text-sm font-medium leading-9 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
        >
          Reset
        </Link>
      </div>
    </form>
  );
}
