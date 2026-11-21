import { Badge, verdictTone, type BadgeTone } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import type {
  Assessment,
  ConfidenceLevel,
  Dispute,
  Fact,
  FactPack,
  PerspectiveRecord,
  ResearchDetail,
  SourceType,
  Verdict,
} from "@/lib/types";

export interface ParsedResearch {
  facts: FactPack | null;
  perspectives: PerspectiveRecord[];
  disputes: Dispute[];
  assessment: Assessment | null;
  models: string[];
  tokens: number;
}

export function parseResearch(run: ResearchDetail): ParsedResearch {
  const byKind = new Map(run.outputs.map((output) => [output.kind, output]));
  const perspectives = (["h1", "h2", "h3", "h4"] as const)
    .map((key) => byKind.get(key)?.output as PerspectiveRecord | undefined)
    .filter((item): item is PerspectiveRecord => Boolean(item));

  return {
    facts: (byKind.get("facts")?.output as FactPack | undefined) ?? null,
    perspectives,
    disputes:
      (byKind.get("disputes")?.output as { disputes?: Dispute[] } | undefined)
        ?.disputes ?? [],
    assessment: (byKind.get("h5")?.output as Assessment | undefined) ?? null,
    models: Array.from(
      new Set(
        run.outputs
          .map((output) => output.model)
          .filter((model): model is string => Boolean(model)),
      ),
    ),
    tokens: run.outputs.reduce(
      (sum, output) =>
        sum + (output.input_tokens ?? 0) + (output.output_tokens ?? 0),
      0,
    ),
  };
}

const CONFIDENCE_TONE: Record<ConfidenceLevel, BadgeTone> = {
  high: "success",
  medium: "warning",
  low: "danger",
};

const SOURCE_TONE: Record<SourceType, BadgeTone> = {
  official: "success",
  exchange: "info",
  secondary: "warning",
  database: "neutral",
};

const SOURCE_LABEL: Record<SourceType, string> = {
  official: "Official",
  exchange: "Exchange",
  secondary: "Secondary",
  database: "This app",
};

function CitationChips({ ids }: { ids: string[] }) {
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1 align-middle">
      {ids.map((id) => (
        <a
          key={id}
          href={`#fact-${id}`}
          className="rounded border border-border bg-muted px-1 font-mono text-[10px] text-muted-foreground hover:border-primary hover:text-primary"
        >
          {id}
        </a>
      ))}
    </span>
  );
}

function List({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <div>
      <h4 className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </h4>
      <ul className="mt-1.5 space-y-1 text-sm leading-6">
        {items.map((item) => (
          <li key={item} className="flex gap-2">
            <span aria-hidden="true" className="text-muted-foreground">
              •
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AssessmentCard({
  assessment,
  deterministic,
}: {
  assessment: Assessment;
  deterministic: { score: number; verdict: Verdict } | null;
}) {
  return (
    <Card>
      <CardHeader
        title="Overall assessment (H5)"
        description="AI synthesis of the four perspectives and the dispute log, shown beside the rule-based score — it never replaces it."
      />
      <CardContent className="space-y-5">
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="rounded-lg border border-border p-4">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              AI verdict
            </p>
            <div className="mt-2 flex items-center gap-2">
              <Badge tone={verdictTone(assessment.verdict)} className="text-sm">
                {assessment.verdict}
              </Badge>
              <Badge tone={CONFIDENCE_TONE[assessment.confidence.level]}>
                {assessment.confidence.level} confidence
              </Badge>
            </div>
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              {assessment.confidence.reason}
            </p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
              Rule-based score
            </p>
            {deterministic ? (
              <div className="mt-2 flex items-center gap-2">
                <Badge tone={verdictTone(deterministic.verdict)} className="text-sm">
                  {deterministic.verdict}
                </Badge>
                <span className="text-sm font-semibold">
                  {deterministic.score.toFixed(1)} / 100
                </span>
              </div>
            ) : (
              <p className="mt-2 text-sm text-muted-foreground">
                Not computed — run <code className="font-mono text-xs">analyze</code>.
              </p>
            )}
            <p className="mt-2 text-xs leading-5 text-muted-foreground">
              Deterministic GMP/subscription/valuation screen.
            </p>
          </div>
        </div>

        <p className="text-sm leading-7">{assessment.conclusion}</p>

        <div className="grid gap-5 sm:grid-cols-2">
          <List title="Top strengths" items={assessment.strengths} />
          <List title="Top risks" items={assessment.risks} />
        </div>
        <List title="What would change the view" items={assessment.what_would_change} />
        {assessment.notes && assessment.notes.length > 0 ? (
          <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
            Pipeline notes: {assessment.notes.join(" · ")}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function PerspectiveCard({
  perspective,
  disputes,
}: {
  perspective: PerspectiveRecord;
  disputes: Dispute[];
}) {
  const disputed = new Map(
    disputes
      .filter((dispute) => dispute.perspective === perspective.key)
      .map((dispute) => [dispute.finding_id, dispute]),
  );

  return (
    <Card className="flex flex-col">
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <span className="font-mono text-xs text-muted-foreground">
              {perspective.key.toUpperCase()}
            </span>
            {perspective.title}
          </span>
        }
        actions={
          perspective.error ? (
            <Badge tone="danger">failed</Badge>
          ) : (
            <Badge tone={CONFIDENCE_TONE[perspective.confidence.level]}>
              {perspective.confidence.level}
            </Badge>
          )
        }
      />
      <CardContent className="flex-1 space-y-4">
        {perspective.error ? (
          <p className="text-sm text-danger">{perspective.error}</p>
        ) : (
          <>
            <p className="text-sm font-medium leading-6">
              {perspective.conclusion}
            </p>
            <ul className="space-y-2 text-sm leading-6">
              {perspective.evidence.map((item, index) => {
                const dispute = disputed.get(`${perspective.key}.${index + 1}`);
                return (
                  <li key={item.point} className="flex gap-2">
                    <span aria-hidden="true" className="text-muted-foreground">
                      •
                    </span>
                    <span>
                      <span className={dispute ? "decoration-warning/60 underline decoration-wavy underline-offset-4" : undefined}>
                        {item.point}
                      </span>
                      <CitationChips ids={item.fact_ids} />
                      {dispute ? (
                        <span className="mt-1 block text-xs text-warning">
                          Verifier: {dispute.stance} — {dispute.verifier_reason}
                        </span>
                      ) : null}
                    </span>
                  </li>
                );
              })}
            </ul>
            <List title="Missing information" items={perspective.missing_information} />
            {perspective.dropped_evidence.length > 0 ? (
              <p className="text-xs text-muted-foreground">
                {perspective.dropped_evidence.length} uncited point
                {perspective.dropped_evidence.length === 1 ? "" : "s"} removed
                by the citation gate.
              </p>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

const RULING_LABEL: Record<Dispute["ruling"], { label: string; tone: BadgeTone }> = {
  uphold_finding: { label: "Finding upheld", tone: "success" },
  uphold_verifier: { label: "Verifier upheld", tone: "warning" },
  unresolved: { label: "Unresolved", tone: "neutral" },
};

export function DisputeLog({ disputes }: { disputes: Dispute[] }) {
  return (
    <Card>
      <CardHeader
        title="Dispute log"
        description="Findings the independent verifier did not accept. Rulings come from the challenger when it is configured."
      />
      <CardContent>
        {disputes.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            The verifier accepted every finding.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {disputes.map((dispute) => (
              <li key={dispute.finding_id} className="space-y-1.5 py-3 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-muted-foreground">
                    {dispute.finding_id}
                  </span>
                  <Badge tone="warning">{dispute.stance}</Badge>
                  <Badge tone={RULING_LABEL[dispute.ruling].tone}>
                    {RULING_LABEL[dispute.ruling].label}
                  </Badge>
                </div>
                <p className="text-sm font-medium">{dispute.finding}</p>
                <p className="text-sm text-muted-foreground">
                  Verifier: {dispute.verifier_reason}
                </p>
                {dispute.ruling_reason ? (
                  <p className="text-sm text-muted-foreground">
                    Ruling: {dispute.ruling_reason}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function hostOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

function FactRow({ fact }: { fact: Fact }) {
  return (
    <li id={`fact-${fact.id}`} className="scroll-mt-24 py-2.5 target:bg-primary/5">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 w-8 shrink-0 font-mono text-xs text-muted-foreground">
          {fact.id}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm leading-6">
            {fact.claim}
            {fact.value ? (
              <span className="font-semibold">: {fact.value}</span>
            ) : null}
            {fact.period ? (
              <span className="text-muted-foreground"> ({fact.period})</span>
            ) : null}
          </p>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
            <Badge tone={SOURCE_TONE[fact.source_type]}>
              {SOURCE_LABEL[fact.source_type]}
            </Badge>
            <span className="capitalize">{fact.category}</span>
            {fact.source_url ? (
              <a
                href={fact.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="max-w-full truncate text-primary underline-offset-4 hover:underline"
              >
                {fact.source_title || hostOf(fact.source_url)}
              </a>
            ) : fact.source_title ? (
              <span>{fact.source_title}</span>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
}

export function FactList({ pack }: { pack: FactPack }) {
  const web = pack.facts.filter((fact) => fact.source_type !== "database");
  const own = pack.facts.filter((fact) => fact.source_type === "database");

  return (
    <Card>
      <CardHeader
        title={`Evidence (${pack.facts.length} facts)`}
        description={`Gathered ${formatDateTime(pack.gathered_at)}. Web facts are unverified until checked against the RHP — secondary sources are flagged.`}
        actions={
          pack.rhp_url ? (
            <a
              href={pack.rhp_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs font-medium text-primary underline-offset-4 hover:underline"
            >
              Open RHP
            </a>
          ) : undefined
        }
      />
      <CardContent className="space-y-4">
        <details open={web.length <= 12}>
          <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            From the web ({web.length})
          </summary>
          <ul className="mt-2 divide-y divide-border">
            {web.map((fact) => (
              <FactRow key={fact.id} fact={fact} />
            ))}
          </ul>
        </details>
        {own.length > 0 ? (
          <details>
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              From this app&apos;s data ({own.length})
            </summary>
            <ul className="mt-2 divide-y divide-border">
              {own.map((fact) => (
                <FactRow key={fact.id} fact={fact} />
              ))}
            </ul>
          </details>
        ) : null}
        {pack.gaps.length > 0 ? (
          <List title="Not found during research" items={pack.gaps} />
        ) : null}
      </CardContent>
    </Card>
  );
}

export function ResearchView({
  run,
  deterministic,
}: {
  run: ResearchDetail;
  deterministic: { score: number; verdict: Verdict } | null;
}) {
  const parsed = parseResearch(run);

  return (
    <div className="space-y-5">
      {parsed.assessment ? (
        <AssessmentCard
          assessment={parsed.assessment}
          deterministic={deterministic}
        />
      ) : null}

      {parsed.perspectives.length > 0 ? (
        <div className="grid gap-5 lg:grid-cols-2">
          {parsed.perspectives.map((perspective) => (
            <PerspectiveCard
              key={perspective.key}
              perspective={perspective}
              disputes={parsed.disputes}
            />
          ))}
        </div>
      ) : null}

      {parsed.assessment ? <DisputeLog disputes={parsed.disputes} /> : null}
      {parsed.facts ? <FactList pack={parsed.facts} /> : null}

      <p className="text-xs leading-5 text-muted-foreground">
        Run #{run.id} · finished {formatDateTime(run.finished_at)} · prompt{" "}
        {run.prompt_version} · models {parsed.models.join(", ") || "—"} ·{" "}
        {parsed.tokens.toLocaleString("en-IN")} tokens. AI output can be wrong;
        verify against the RHP. Not investment advice.
      </p>
    </div>
  );
}
