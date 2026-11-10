import Link from "next/link";

const STATUS_OPTIONS = ["Open", "Upcoming", "Closed", "Listed"] as const;

export function IpoFilters({
  minGmp,
  status,
}: {
  minGmp: number;
  status?: string;
}) {
  return (
    <form
      method="get"
      className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4 shadow-sm sm:flex-row sm:flex-wrap sm:items-end"
    >
      <label className="flex flex-col gap-1.5 text-xs font-medium text-muted-foreground">
        Minimum GMP %
        <input
          type="number"
          name="min_gmp"
          defaultValue={minGmp}
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
          defaultValue={status ?? ""}
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
