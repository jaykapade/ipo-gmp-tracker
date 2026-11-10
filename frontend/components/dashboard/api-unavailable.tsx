import { API_BASE_URL, ApiError } from "@/lib/api";

export function ApiUnavailable({ error }: { error: ApiError }) {
  return (
    <div className="rounded-xl border border-warning/40 bg-warning/10 p-5 text-sm">
      <p className="font-semibold text-warning">Backend not reachable</p>
      <p className="mt-1 leading-6 text-muted-foreground">
        {error.message} Start it from the repository root:
      </p>
      <pre className="mt-3 overflow-x-auto rounded-lg bg-background/70 p-3 font-mono text-xs">
        cd backend{"\n"}
        python -m src.main serve
      </pre>
      <p className="mt-3 text-xs text-muted-foreground">
        Expected API: <code className="font-mono">{API_BASE_URL}</code>. Change{" "}
        <code className="font-mono">NEXT_PUBLIC_API_BASE_URL</code> in{" "}
        <code className="font-mono">frontend/.env.local</code> to point elsewhere.
      </p>
    </div>
  );
}
