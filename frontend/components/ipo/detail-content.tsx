import Link from "next/link";
import { notFound } from "next/navigation";

import { ApiUnavailable } from "@/components/dashboard/api-unavailable";
import { ResearchBadge } from "@/components/dashboard/ipo-table";
import { ResearchPanel } from "@/components/research/research-panel";
import { PageHeader } from "@/components/shell/page-header";
import { Badge, statusTone, verdictTone } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Stat } from "@/components/ui/stat";
import { ApiError, api } from "@/lib/api";
import {
  formatCurrency,
  formatDate,
  formatDateTime,
  formatIssueSize,
  formatMultiple,
  formatNumber,
  formatPercent,
  formatPriceBand,
  formatText,
} from "@/lib/format";
import type { IPODetail, ResearchDetail } from "@/lib/types";
import { cn } from "@/lib/utils";

import { AnalysisPanel } from "./analysis-panel";
import { GmpChart } from "./gmp-chart";
import { GmpHistory } from "./gmp-history";

function DetailRow({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-right font-medium">{children}</dd>
    </div>
  );
}

function ExternalLink({ href }: { href: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-primary underline-offset-4 hover:underline"
    >
      Open source
    </a>
  );
}

function IssueDetails({ ipo }: { ipo: IPODetail }) {
  return (
    <Card>
      <CardHeader title="Issue details" />
      <CardContent>
        <dl className="space-y-3 text-sm">
          <DetailRow label="Status">
            <Badge tone={statusTone(ipo.status)}>
              {formatText(ipo.status)}
            </Badge>
          </DetailRow>
          <DetailRow label="Category">
            {formatText(ipo.category)}
          </DetailRow>
          <DetailRow label="Sector">{formatText(ipo.sector)}</DetailRow>
          <DetailRow label="Exchange">
            {formatText(ipo.exchange)}
          </DetailRow>
          <DetailRow label="Price band">
            {formatPriceBand(
              ipo.issue_price_lower,
              ipo.issue_price_upper,
              ipo.issue_price,
            )}
          </DetailRow>
          <DetailRow label="Lot size">
            {formatText(ipo.lot_size)}
          </DetailRow>
          <DetailRow label="P/E">{formatNumber(ipo.pe)}</DetailRow>
          <DetailRow label="Est. listing">
            {formatCurrency(ipo.estimated_listing_price)}
          </DetailRow>
          <DetailRow label="Opens">{formatDate(ipo.open_date)}</DetailRow>
          <DetailRow label="Closes">{formatDate(ipo.close_date)}</DetailRow>
          <DetailRow label="Lists">
            {formatDate(ipo.listing_date)}
          </DetailRow>
          <DetailRow label="RHP">
            {ipo.rhp_url ? (
              <ExternalLink href={ipo.rhp_url} />
            ) : (
              <span className="text-muted-foreground">Not stored</span>
            )}
          </DetailRow>
        </dl>
      </CardContent>
    </Card>
  );
}

function Sources({ ipo }: { ipo: IPODetail }) {
  return (
    <Card>
      <CardHeader
        title="Sources"
        description="Where this IPO has been observed"
      />
      <CardContent>
        {ipo.sources.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No source provenance recorded.
          </p>
        ) : (
          <ul className="space-y-4 text-sm">
            {ipo.sources.map((source) => (
              <li key={`${source.source}-${source.source_ipo_id ?? ""}`}>
                <div className="flex items-center justify-between gap-3">
                  <span className="font-medium">{source.source}</span>
                  {source.source_url ? (
                    <ExternalLink href={source.source_url} />
                  ) : null}
                </div>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
                  First seen {formatDateTime(source.first_seen_at)}
                  <br />
                  Last seen {formatDateTime(source.last_seen_at)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

type Tab = "overview" | "research";

function Tabs({ id, active }: { id: number; active: Tab }) {
  const tabs: { key: Tab; label: string; href: string }[] = [
    { key: "overview", label: "Overview", href: `/ipos/${id}` },
    { key: "research", label: "AI research", href: `/ipos/${id}?tab=research` },
  ];
  return (
    <nav aria-label="IPO sections" className="flex gap-1 border-b border-border">
      {tabs.map((tab) => (
        <Link
          key={tab.key}
          href={tab.href}
          scroll={false}
          aria-current={tab.key === active ? "page" : undefined}
          className={cn(
            "-mb-px border-b-2 px-3 py-2.5 text-sm font-medium transition-colors",
            tab.key === active
              ? "border-primary text-foreground"
              : "border-transparent text-muted-foreground hover:text-foreground",
          )}
        >
          {tab.label}
        </Link>
      ))}
    </nav>
  );
}

async function ResearchTab({ ipo }: { ipo: IPODetail }) {
  const [research, health] = await Promise.all([
    api.getResearch(ipo.id).catch((): ResearchDetail | null => null),
    api.health().catch(() => null),
  ]);
  const analysis = ipo.latest_analysis;

  return (
    <ResearchPanel
      ipoId={ipo.id}
      initial={research}
      aiEnabled={Boolean(health?.ai.enabled)}
      deterministic={
        analysis ? { score: analysis.score, verdict: analysis.verdict } : null
      }
    />
  );
}

export async function IpoDetailContent({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { id } = await params;
  const tab: Tab = (await searchParams).tab === "research" ? "research" : "overview";

  let ipo: IPODetail;
  try {
    ipo = await api.getIpo(id);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      notFound();
    }
    if (error instanceof ApiError) {
      return <ApiUnavailable error={error} />;
    }
    throw error;
  }

  const analysis = ipo.latest_analysis;

  return (
    <div className="space-y-6">
      <Link
        href="/"
        className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        ← Back to dashboard
      </Link>

      <PageHeader
        eyebrow={[ipo.category, ipo.sector].filter(Boolean).join(" · ")}
        title={ipo.name}
        description={
          <>
            {ipo.exchange ? `${ipo.exchange} · ` : ""}
            Closes {formatDate(ipo.close_date)} · latest GMP{" "}
            {formatPercent(ipo.gmp_percent)}
            {ipo.gmp_percent_derived ? " (derived)" : ""}
          </>
        }
        actions={
          <>
            <Badge tone={statusTone(ipo.status)}>
              {formatText(ipo.status)}
            </Badge>
            {analysis ? (
              <Badge tone={verdictTone(analysis.verdict)}>
                Score {analysis.verdict} · {analysis.score.toFixed(1)}
              </Badge>
            ) : null}
            <ResearchBadge ipo={ipo} />
          </>
        }
      />

      <Tabs id={ipo.id} active={tab} />

      {tab === "research" ? (
        <ResearchTab ipo={ipo} />
      ) : (
      <>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Stat
          label="Latest GMP"
          value={
            <span
              className={
                ipo.gmp_percent == null
                  ? undefined
                  : ipo.gmp_percent >= 20
                    ? "text-success"
                    : "text-warning"
              }
            >
              {formatPercent(ipo.gmp_percent)}
            </span>
          }
          hint={`${formatCurrency(ipo.gmp)} · ${ipo.latest_gmp_source ?? "source unknown"}`}
        />
        <Stat
          label="Issue price"
          value={formatPriceBand(
            ipo.issue_price_lower,
            ipo.issue_price_upper,
            ipo.issue_price,
          )}
          hint="Lower – upper band"
        />
        <Stat
          label="Issue size"
          value={formatIssueSize(ipo.ipo_size_cr)}
          hint={ipo.lot_size ?? "Lot size not stored"}
        />
        <Stat
          label="Subscription"
          value={formatMultiple(ipo.subscription)}
          hint={ipo.pe == null ? "P/E not stored" : `P/E ${ipo.pe}`}
        />
      </div>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <div className="space-y-5">
          <Card>
            <CardHeader
              title="GMP history"
              description={`${ipo.gmp_history.length} observations · latest ${formatDateTime(ipo.latest_gmp_recorded_at)}`}
            />
            <GmpChart history={ipo.gmp_history} />
            <div className="border-t border-border">
              <GmpHistory history={ipo.gmp_history} />
            </div>
          </Card>

          <AnalysisPanel analysis={analysis} />
        </div>

        <div className="space-y-5">
          <IssueDetails ipo={ipo} />
          <Sources ipo={ipo} />
        </div>
      </div>
      </>
      )}

      <p className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-xs leading-5 text-muted-foreground">
        <strong className="font-semibold text-warning">
          Not investment advice.
        </strong>{" "}
        GMP is an unofficial grey-market signal and can disappear before
        listing. Verify every fact against the official RHP and NSE/BSE filings
        before applying.
      </p>
    </div>
  );
}
