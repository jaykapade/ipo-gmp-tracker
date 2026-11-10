import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">
        404
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">Page not found</h1>
      <p className="max-w-md text-sm leading-6 text-muted-foreground">
        That route or IPO does not exist in the current database. It may have
        been removed, or the link may be wrong.
      </p>
      <Link
        href="/"
        className="mt-2 h-9 rounded-md bg-primary px-4 text-sm font-medium leading-9 text-primary-foreground transition-opacity hover:opacity-90"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
