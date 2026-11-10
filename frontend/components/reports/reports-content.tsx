import { ApiUnavailable } from "@/components/dashboard/api-unavailable";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { ApiError, api } from "@/lib/api";
import { formatDateTime, formatFileSize } from "@/lib/format";

export async function ReportsContent() {
  let reports;
  try {
    reports = await api.listReports();
  } catch (error) {
    if (error instanceof ApiError) {
      return <ApiUnavailable error={error} />;
    }
    throw error;
  }

  if (reports.length === 0) {
    return (
      <Card>
        <EmptyState
          title="No reports generated yet"
          description="Reports are written by the backend pipeline. Run `python -m src.main report` from backend/, or call the token-protected POST /api/reports endpoint."
          action={{ href: "/", label: "Back to dashboard" }}
        />
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Generated reports"
        description={`${reports.length} PDF report${reports.length === 1 ? "" : "s"} · newest first`}
      />
      <ul className="divide-y divide-border">
        {reports.map((report) => (
          <li
            key={report.filename}
            className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="truncate font-mono text-sm font-medium">
                {report.filename}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {formatFileSize(report.size_bytes)} · generated{" "}
                {formatDateTime(report.modified_at)}
              </p>
            </div>
            <a
              href={api.reportDownloadUrl(report.filename)}
              className="inline-flex h-9 shrink-0 items-center rounded-md border border-border px-3 text-sm font-medium transition-colors hover:bg-muted"
            >
              Download PDF
            </a>
          </li>
        ))}
      </ul>
    </Card>
  );
}
