import { Badge, checklistTone, verdictTone } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import type { IPOAnalysis } from "@/lib/types";

function BulletList({
  title,
  items,
}: {
  title: string;
  items: string[];
}) {
  return (
    <div>
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h3>
      {items.length > 0 ? (
        <ul className="mt-2 space-y-1.5 text-sm leading-6">
          {items.map((item) => (
            <li key={item} className="flex gap-2">
              <span aria-hidden="true" className="text-muted-foreground">
                •
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-muted-foreground">None recorded.</p>
      )}
    </div>
  );
}

export function AnalysisPanel({ analysis }: { analysis: IPOAnalysis | null }) {
  if (!analysis) {
    return (
      <Card>
        <CardHeader
          title="Analysis"
          description="Deterministic score, checklist and narrative"
        />
        <CardContent>
          <p className="text-sm leading-6 text-muted-foreground">
            No analysis has been stored for this IPO yet. Run{" "}
            <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
              python -m src.main analyze
            </code>{" "}
            from <code className="font-mono text-xs">backend/</code>, then
            refresh this page.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader
        title="Latest analysis"
        description={`Generated ${formatDateTime(analysis.generated_at)} · transparent weighted score, no black box`}
        actions={
          <>
            <Badge tone={verdictTone(analysis.verdict)}>
              {analysis.verdict}
            </Badge>
            <Badge tone="primary">{analysis.score.toFixed(1)} / 100</Badge>
          </>
        }
      />

      <CardContent className="space-y-6">
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Score breakdown
          </h3>
          <div className="mt-3 space-y-3">
            {analysis.factors.map((factor) => (
              <div key={factor.key}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="font-medium">
                    {factor.label}
                    <span className="ml-2 text-xs text-muted-foreground">
                      weight {(factor.weight * 100).toFixed(0)}%
                    </span>
                  </span>
                  <span className="font-mono text-xs">
                    {factor.score.toFixed(1)}
                  </span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full bg-primary"
                    style={{ width: `${factor.score}%` }}
                  />
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  {factor.explanation}
                  {!factor.data_available ? " (neutral — data missing)" : ""}
                </p>
              </div>
            ))}
          </div>
        </section>

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Checklist
          </h3>
          <div className="mt-2 divide-y divide-border">
            {analysis.checklist.map((item) => (
              <div
                key={item.key}
                className="flex flex-col gap-1 py-2.5 sm:flex-row sm:items-start sm:justify-between sm:gap-4"
              >
                <div>
                  <p className="text-sm font-medium">{item.label}</p>
                  <p className="mt-0.5 text-xs leading-5 text-muted-foreground">
                    {item.detail}
                  </p>
                </div>
                <Badge tone={checklistTone(item.status)}>
                  {item.status.toUpperCase()}
                </Badge>
              </div>
            ))}
          </div>
        </section>

        <section className="grid gap-5 sm:grid-cols-3">
          <BulletList title="Strengths" items={analysis.strengths} />
          <BulletList title="Risks" items={analysis.risks} />
          <BulletList title="Data gaps" items={analysis.data_gaps} />
        </section>
      </CardContent>
    </Card>
  );
}
