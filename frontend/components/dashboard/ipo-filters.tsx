"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";

import type { CategoryFilter } from "@/lib/api";
import {
  CATEGORY_LABEL,
  dashboardHref,
  GMP_PRESETS,
  hasActiveFilters,
  type DashboardQuery,
} from "@/lib/dashboard-query";
import type { IPOFacets } from "@/lib/types";
import { cn } from "@/lib/utils";

const SEARCH_DEBOUNCE_MS = 350;

function Segment({
  active,
  href,
  onNavigate,
  children,
}: {
  active: boolean;
  href: string;
  onNavigate: (href: string) => void;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      scroll={false}
      aria-pressed={active}
      onClick={(event) => {
        event.preventDefault();
        onNavigate(href);
      }}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-md px-3 text-sm font-medium transition-colors",
        active
          ? "bg-card text-foreground shadow-sm ring-1 ring-border"
          : "text-muted-foreground hover:text-foreground",
      )}
    >
      {children}
    </Link>
  );
}

function Count({ value }: { value: number | undefined }) {
  if (value == null) return null;
  return (
    <span className="rounded bg-muted px-1.5 text-[11px] tabular-nums text-muted-foreground">
      {value}
    </span>
  );
}

function FilterGroup({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <div className="flex flex-wrap items-center gap-1 rounded-lg bg-muted/70 p-1">
        {children}
      </div>
    </div>
  );
}

/**
 * Dashboard filter bar.
 *
 * Every control is a link or a GET form field, so the bar works without
 * JavaScript; with JS, changes apply instantly via `router.replace`. Options
 * come from `/api/ipos/facets`, so values that cannot match anything are
 * never offered.
 */
export function IpoFilters({
  query,
  facets,
}: {
  query: DashboardQuery;
  facets: IPOFacets | null;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [search, setSearch] = useState(query.q ?? "");
  const lastSubmitted = useRef(query.q ?? "");

  const navigate = (href: string) => {
    startTransition(() => router.replace(href, { scroll: false }));
  };

  // Debounced live search.
  useEffect(() => {
    const value = search.trim();
    if (value === lastSubmitted.current) return;
    const timer = window.setTimeout(() => {
      lastSubmitted.current = value;
      navigate(dashboardHref(query, { q: value || undefined }));
    }, SEARCH_DEBOUNCE_MS);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- query is URL state
  }, [search]);

  const categoryCount = (value: CategoryFilter) =>
    facets?.categories.find((item) => item.value === value)?.count;
  const floor = facets?.screen_floor ?? 20;
  const presets = Array.from(new Set([...GMP_PRESETS, floor])).sort(
    (a, b) => a - b,
  );
  const statuses = (facets?.statuses ?? []).filter((item) => item.value);
  const unknownStatus = facets?.statuses.find((item) => !item.value)?.count;
  const showStatus = statuses.length > 1 || Boolean(query.status);

  const chips: { label: string; href: string }[] = [];
  if (query.q) chips.push({ label: `“${query.q}”`, href: dashboardHref(query, { q: undefined }) });
  if (query.category) {
    chips.push({
      label: CATEGORY_LABEL[query.category],
      href: dashboardHref(query, { category: undefined }),
    });
  }
  if (query.minGmp != null) {
    chips.push({
      label: `GMP ≥ ${query.minGmp}%`,
      href: dashboardHref(query, { minGmp: null }),
    });
  }
  if (query.status) {
    chips.push({
      label: `Status: ${query.status}`,
      href: dashboardHref(query, { status: undefined }),
    });
  }
  if (query.researched) {
    chips.push({
      label: "Has AI research",
      href: dashboardHref(query, { researched: false }),
    });
  }

  return (
    <section
      aria-label="Filters"
      aria-busy={isPending}
      className={cn(
        "space-y-4 rounded-xl border border-border bg-card p-4 shadow-sm transition-opacity",
        isPending && "opacity-70",
      )}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:flex-wrap lg:items-end">
        <form
          method="get"
          action="/"
          role="search"
          className="flex flex-col gap-1.5 lg:min-w-64 lg:flex-1"
          onSubmit={(event) => {
            event.preventDefault();
            lastSubmitted.current = search.trim();
            navigate(dashboardHref(query, { q: search.trim() || undefined }));
          }}
        >
          <label
            htmlFor="ipo-search"
            className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground"
          >
            Search
          </label>
          <input
            id="ipo-search"
            type="search"
            name="q"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            maxLength={100}
            placeholder="Company name…"
            className="h-10 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/70"
          />
          {/* Preserve the other filters when the form submits without JS. */}
          {query.minGmp != null ? (
            <input type="hidden" name="min_gmp" value={query.minGmp} />
          ) : null}
          {query.category ? (
            <input type="hidden" name="category" value={query.category} />
          ) : null}
          {query.status ? (
            <input type="hidden" name="status" value={query.status} />
          ) : null}
          {query.researched ? (
            <input type="hidden" name="researched" value="1" />
          ) : null}
        </form>

        <FilterGroup label="Board">
          <Segment
            active={!query.category}
            href={dashboardHref(query, { category: undefined })}
            onNavigate={navigate}
          >
            All <Count value={facets?.total} />
          </Segment>
          {(["mainboard", "sme"] as const).map((value) => (
            <Segment
              key={value}
              active={query.category === value}
              href={dashboardHref(query, { category: value })}
              onNavigate={navigate}
            >
              {CATEGORY_LABEL[value]} <Count value={categoryCount(value) ?? 0} />
            </Segment>
          ))}
        </FilterGroup>

        <FilterGroup label="Latest GMP">
          <Segment
            active={query.minGmp == null}
            href={dashboardHref(query, { minGmp: null })}
            onNavigate={navigate}
          >
            Any
          </Segment>
          {presets.map((value) => (
            <Segment
              key={value}
              active={query.minGmp === value}
              href={dashboardHref(query, { minGmp: value })}
              onNavigate={navigate}
            >
              ≥ {value}%
              {value === floor ? (
                <span className="text-[10px] uppercase text-primary">screen</span>
              ) : null}
            </Segment>
          ))}
        </FilterGroup>

        {showStatus ? (
          <FilterGroup label="Status">
            <Segment
              active={!query.status}
              href={dashboardHref(query, { status: undefined })}
              onNavigate={navigate}
            >
              All
            </Segment>
            {statuses.map((item) => (
              <Segment
                key={item.value}
                active={query.status === item.value}
                href={dashboardHref(query, { status: item.value ?? undefined })}
                onNavigate={navigate}
              >
                <span className="capitalize">{item.value}</span>
                <Count value={item.count} />
              </Segment>
            ))}
          </FilterGroup>
        ) : null}

        <FilterGroup label="AI research">
          <Segment
            active={!query.researched}
            href={dashboardHref(query, { researched: false })}
            onNavigate={navigate}
          >
            All
          </Segment>
          <Segment
            active={query.researched}
            href={dashboardHref(query, { researched: true })}
            onNavigate={navigate}
          >
            Researched <Count value={facets?.researched} />
          </Segment>
        </FilterGroup>
      </div>

      {chips.length > 0 || unknownStatus ? (
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3 text-xs">
          {chips.map((chip) => (
            <Link
              key={chip.label}
              href={chip.href}
              scroll={false}
              onClick={(event) => {
                event.preventDefault();
                if (chip.label.startsWith("“")) {
                  setSearch("");
                  lastSubmitted.current = "";
                }
                navigate(chip.href);
              }}
              className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-2.5 py-1 font-medium text-primary hover:bg-primary/15"
              aria-label={`Remove filter ${chip.label}`}
            >
              {chip.label}
              <span aria-hidden="true">×</span>
            </Link>
          ))}
          {hasActiveFilters(query) ? (
            <Link
              href="/"
              scroll={false}
              onClick={(event) => {
                event.preventDefault();
                setSearch("");
                lastSubmitted.current = "";
                navigate("/");
              }}
              className="font-medium text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
            >
              Clear all
            </Link>
          ) : null}
          {unknownStatus ? (
            <span className="ml-auto text-muted-foreground">
              {unknownStatus} IPO{unknownStatus === 1 ? "" : "s"} without a
              reported status
            </span>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
