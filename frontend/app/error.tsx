"use client";

import { useEffect } from "react";

export default function AppError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-center">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-danger">
        Something went wrong
      </p>
      <h1 className="text-2xl font-semibold tracking-tight">
        This page could not be rendered
      </h1>
      <p className="max-w-md text-sm leading-6 text-muted-foreground">
        An unexpected error occurred. Retry the request; if it keeps failing,
        check that the IPO Checker API is running and reachable.
      </p>
      {error.digest ? (
        <p className="font-mono text-xs text-muted-foreground">
          Digest: {error.digest}
        </p>
      ) : null}
      <button
        type="button"
        onClick={() => retry()}
        className="mt-2 h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
      >
        Try again
      </button>
    </div>
  );
}
