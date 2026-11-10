import { EmptyState } from "@/components/ui/empty-state";
import { Stat } from "@/components/ui/stat";
import { Card } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

import { ApiUnavailable } from "./api-unavailable";
import { IpoFilters } from "./ipo-filters";
import { IpoTable } from "./ipo-table";

const DEFAULT_MIN_GMP = 20;

function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

function parseMinGmp(value: string | string[] | undefined): number {
  const raw = firstValue(value);
  if (raw == null || raw.trim() === "") return DEFAULT_MIN_GMP;

  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : DEFAULT_MIN_GMP;
}

export async function DashboardContent({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const minGmp = parseMinGmp(params.min_gmp);
  const status = firstValue(params.status) || undefined;

  let page;
  try {
    page = await api.listIpos({ minGmpPercent: minGmp, status });
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable error={error} />;
    }
    throw error;
  }

  const latestUpdate = page.items
    .map((ipo) => ipo.latest_gmp_recorded_at)
    .filter((value): value is string => Boolean(value))
    .sort()
    .at(-1);

  return (
    <div className="space-y-5">
      <IpoFilters minGmp={minGmp} status={status} />

      <div className="grid gap-3 sm:grid-cols-3">
        <Stat
          label="Matching IPOs"
          value={page.total}
          hint={status ? `Status: ${status}` : "All statuses"}
        />
        <Stat
          label="Screening floor"
          value={`${minGmp}%`}
          hint="Latest GMP percentage"
        />
        <Stat
          label="Latest GMP update"
          value={formatDateTime(latestUpdate)}
          hint="Newest observation in this view"
        />
      </div>

      <Card>
        {page.items.length > 0 ? (
          <>
            <IpoTable items={page.items} />
            {page.total > page.items.length ? (
              <p className="border-t border-border px-5 py-3 text-xs text-muted-foreground">
                Showing the first {page.items.length} of {page.total} matching
                IPOs. Narrow the filters to see the rest.
              </p>
            ) : null}
          </>
        ) : (
          <EmptyState
            title="No IPOs match this screen"
            description={`Nothing currently has a latest GMP of ${minGmp}% or more with these filters. Lower the threshold, or run a scrape if the database is empty.`}
            action={{ href: "/reports", label: "View reports" }}
          />
        )}
      </Card>

      <p className="text-xs leading-5 text-muted-foreground">
        The list is ordered by company name. The GMP filter uses the latest
        observation per IPO; a derived percentage is calculated as GMP ÷ issue
        price and marked accordingly.
      </p>
    </div>
  );
}
