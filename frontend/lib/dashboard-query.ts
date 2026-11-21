/**
 * Dashboard URL state: one place that parses `searchParams` and builds links,
 * shared by the server page, the filter bar and the sortable table headers.
 */

import {
  IPO_SORT_FIELDS,
  type CategoryFilter,
  type IpoSortField,
  type SortOrder,
} from "@/lib/api";

export interface DashboardQuery {
  q?: string;
  /** `null` means "any GMP" (no floor). */
  minGmp: number | null;
  category?: CategoryFilter;
  status?: string;
  researched: boolean;
  sort: IpoSortField;
  order: SortOrder;
}

export const DEFAULT_QUERY: DashboardQuery = {
  minGmp: null,
  researched: false,
  sort: "gmp_percent",
  order: "desc",
};

/** GMP presets shown as chips; the screen floor is inserted from facets. */
export const GMP_PRESETS = [10, 30] as const;

type RawParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined): string | undefined {
  const raw = Array.isArray(value) ? value[0] : value;
  return raw?.trim() ? raw.trim() : undefined;
}

export function parseDashboardQuery(params: RawParams): DashboardQuery {
  const rawGmp = first(params.min_gmp);
  const parsedGmp = rawGmp == null ? NaN : Number(rawGmp);
  const category = first(params.category);
  const sort = first(params.sort);

  return {
    q: first(params.q)?.slice(0, 100),
    minGmp: Number.isFinite(parsedGmp) && parsedGmp > 0 ? parsedGmp : null,
    category:
      category === "mainboard" || category === "sme" ? category : undefined,
    status: first(params.status)?.toLowerCase(),
    researched: first(params.researched) === "1",
    sort: IPO_SORT_FIELDS.find((field) => field === sort) ?? DEFAULT_QUERY.sort,
    order:
      first(params.order) === "asc"
        ? "asc"
        : first(params.sort)
          ? "desc"
          : DEFAULT_QUERY.order,
  };
}

/** Build a dashboard URL from a query plus overrides; defaults are omitted. */
export function dashboardHref(
  query: DashboardQuery,
  overrides: Partial<DashboardQuery> = {},
): string {
  const next = { ...query, ...overrides };
  const params = new URLSearchParams();

  if (next.q) params.set("q", next.q);
  if (next.minGmp != null) params.set("min_gmp", String(next.minGmp));
  if (next.category) params.set("category", next.category);
  if (next.status) params.set("status", next.status);
  if (next.researched) params.set("researched", "1");
  if (next.sort !== DEFAULT_QUERY.sort || next.order !== DEFAULT_QUERY.order) {
    params.set("sort", next.sort);
    params.set("order", next.order);
  }

  const search = params.toString();
  return search ? `/?${search}` : "/";
}

export function hasActiveFilters(query: DashboardQuery): boolean {
  return Boolean(
    query.q ||
      query.minGmp != null ||
      query.category ||
      query.status ||
      query.researched,
  );
}

export const CATEGORY_LABEL: Record<CategoryFilter, string> = {
  mainboard: "Mainboard",
  sme: "SME",
};
