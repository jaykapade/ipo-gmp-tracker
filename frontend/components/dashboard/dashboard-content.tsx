import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Stat } from "@/components/ui/stat";
import { API_SORT_LABEL, ApiError, api } from "@/lib/api";
import {
  hasActiveFilters,
  parseDashboardQuery,
} from "@/lib/dashboard-query";
import { formatDateTime } from "@/lib/format";
import type { IPOFacets } from "@/lib/types";

import { ApiUnavailable } from "./api-unavailable";
import { IpoFilters } from "./ipo-filters";
import { IpoTable } from "./ipo-table";

export async function DashboardContent({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const query = parseDashboardQuery(await searchParams);

  let page;
  let facets: IPOFacets | null = null;
  try {
    [page, facets] = await Promise.all([
      api.listIpos({
        q: query.q,
        minGmpPercent: query.minGmp,
        category: query.category,
        status: query.status,
        hasResearch: query.researched ? true : null,
        sort: query.sort,
        order: query.order,
        limit: 200,
      }),
      api.facets().catch(() => null),
    ]);
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable error={error} />;
    }
    throw error;
  }

  const floor = facets?.screen_floor ?? 20;
  const latestUpdate = page.items
    .map((ipo) => ipo.latest_gmp_recorded_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);
  const meetsScreen = page.items.filter(
    (ipo) => ipo.gmp_percent != null && ipo.gmp_percent >= floor,
  ).length;
  const sme = page.items.filter(
    (ipo) => ipo.category?.toUpperCase() === "SME",
  ).length;
  const researched = page.items.filter(
    (ipo) => ipo.research_status === "done" || ipo.research_verdict,
  ).length;

  return (
    <div className="space-y-5">
      <IpoFilters query={query} facets={facets} />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat
          label="In view"
          value={page.total}
          hint={
            facets && hasActiveFilters(query)
              ? `of ${facets.total} tracked`
              : "IPOs tracked"
          }
        />
        <Stat
          label="Meets screen"
          value={meetsScreen}
          hint={`Latest GMP ≥ ${floor}%`}
        />
        <Stat
          label="Mainboard / SME"
          value={`${page.items.length - sme} / ${sme}`}
          hint="In this view"
        />
        <Stat
          label="AI researched"
          value={researched}
          hint={`Latest GMP ${formatDateTime(latestUpdate)}`}
        />
      </div>

      <Card>
        {page.items.length > 0 ? (
          <>
            <IpoTable items={page.items} query={query} floor={floor} />
            {page.total > page.items.length ? (
              <p className="border-t border-border px-5 py-3 text-xs text-muted-foreground">
                Showing the first {page.items.length} of {page.total} IPOs.
                Narrow the filters to see the rest.
              </p>
            ) : null}
          </>
        ) : facets && facets.total === 0 ? (
          <EmptyState
            title="No IPOs yet"
            description="The database is empty. Run `uv run python -m src.main scrape` from backend/ to fetch the current IPOs, then refresh."
          />
        ) : (
          <EmptyState
            title="Nothing matches these filters"
            description="Try a lower GMP threshold, a different board, or clear the search."
            action={{ href: "/", label: "Clear filters" }}
          />
        )}
      </Card>

      <p className="text-xs leading-5 text-muted-foreground">
        Sorted by {API_SORT_LABEL[query.sort]} (
        {query.order === "asc" ? "ascending" : "descending"}) — click a column
        header to change it. GMP uses the latest observation per IPO; values
        marked * are derived as GMP ÷ issue price because the source omitted
        the percentage.
      </p>
    </div>
  );
}
