"use client";

import { useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { formatDateTime } from "@/lib/format";
import type { ResearchDetail, Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ResearchView } from "./research-view";

const POLL_MS = 3000;

const STAGE_LABEL: Record<string, string> = {
  queued: "Queued",
  gather: "Gathering cited facts from the web",
  perspectives: "Writing four isolated perspectives (H1–H4)",
  verify: "Independent verifier checking every finding",
  challenge: "Challenger ruling on disputes",
  synthesis: "Synthesising the overall assessment (H5)",
  done: "Done",
};

const PIPELINE = ["gather", "perspectives", "verify", "challenge", "synthesis"];

function isActive(run: ResearchDetail | null): boolean {
  return run?.status === "queued" || run?.status === "running";
}

function StageProgress({ run }: { run: ResearchDetail }) {
  const current = run.status === "queued" ? -1 : PIPELINE.indexOf(run.stage ?? "");

  return (
    <ol className="space-y-2.5" aria-live="polite">
      {PIPELINE.map((stage, index) => {
        const state =
          run.status === "failed" && index === current
            ? "failed"
            : index < current
              ? "done"
              : index === current
                ? "active"
                : "pending";
        return (
          <li key={stage} className="flex items-center gap-3 text-sm">
            <span
              aria-hidden="true"
              className={cn(
                "grid size-5 shrink-0 place-items-center rounded-full border text-[10px] font-bold",
                state === "done" && "border-success bg-success/15 text-success",
                state === "active" && "animate-pulse border-primary bg-primary/15 text-primary",
                state === "failed" && "border-danger bg-danger/15 text-danger",
                state === "pending" && "border-border text-muted-foreground",
              )}
            >
              {state === "done" ? "✓" : state === "failed" ? "!" : index + 1}
            </span>
            <span
              className={cn(
                state === "pending" ? "text-muted-foreground" : "text-foreground",
                state === "active" && "font-medium",
              )}
            >
              {STAGE_LABEL[stage]}
            </span>
          </li>
        );
      })}
    </ol>
  );
}

/**
 * The "AI Research" tab: start a run (only offered while no completed result
 * exists), follow its stages, and render the newest completed result. Starting goes through the Next route handler
 * (`/api/research/[id]`), which adds the API token server-side.
 */
export function ResearchPanel({
  ipoId,
  initial,
  aiEnabled,
  deterministic,
}: {
  ipoId: number;
  initial: ResearchDetail | null;
  aiEnabled: boolean;
  deterministic: { score: number; verdict: Verdict } | null;
}) {
  const [run, setRun] = useState<ResearchDetail | null>(initial);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const response = await fetch(`/api/research/${ipoId}`, { cache: "no-store" });
    if (response.ok) setRun((await response.json()) as ResearchDetail | null);
  }, [ipoId]);

  useEffect(() => {
    if (!isActive(run)) return;
    const timer = window.setInterval(() => {
      refresh().catch(() => undefined);
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [run, refresh]);

  const start = async () => {
    setStarting(true);
    setError(null);
    try {
      const response = await fetch(`/api/research/${ipoId}`, { method: "POST" });
      if (!response.ok) {
        const body = (await response.json().catch(() => null)) as {
          detail?: string;
        } | null;
        setError(body?.detail ?? `Could not start research (HTTP ${response.status}).`);
        return;
      }
      await refresh();
    } catch {
      setError("Could not reach the frontend server.");
    } finally {
      setStarting(false);
    }
  };

  const completed = run?.status === "done" ? run : run?.latest_completed ?? null;
  const active = isActive(run);

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader
          title="AI research"
          description="Claude gathers cited facts from the web, writes four isolated perspectives, an independent verifier challenges them, and a synthesis is shown beside the rule-based score."
          actions={
            // Research costs subscription quota: offer it only when none exists yet.
            !completed || active ? (
              <button
                type="button"
                onClick={start}
                disabled={!aiEnabled || active || starting}
                className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {active ? "Research running…" : starting ? "Starting…" : "Run AI research"}
              </button>
            ) : undefined
          }
        />
        <CardContent className="space-y-4">
          {!aiEnabled ? (
            <p className="text-sm leading-6 text-muted-foreground">
              AI is off. Set <code className="font-mono text-xs">LLM_ENABLED=true</code>{" "}
              and a provider in <code className="font-mono text-xs">backend/.env</code>{" "}
              (or <code className="font-mono text-xs">.env.local</code>), then restart
              the API.
            </p>
          ) : null}

          {error ? (
            <p role="alert" className="rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {error}
            </p>
          ) : null}

          {run && (active || run.status === "failed") ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                <Badge tone={run.status === "failed" ? "danger" : "info"}>
                  {run.status}
                </Badge>
                <span>
                  Run #{run.id} · started {formatDateTime(run.started_at ?? run.created_at)}
                </span>
              </div>
              <StageProgress run={run} />
              {run.status === "failed" && run.error ? (
                <p className="rounded-md bg-muted px-3 py-2 text-xs text-muted-foreground">
                  {run.error}
                </p>
              ) : null}
              {active ? (
                <p className="text-xs text-muted-foreground">
                  Usually 2–5 minutes. You can leave this page; the run continues
                  on the server.
                </p>
              ) : null}
            </div>
          ) : null}

          {!run && aiEnabled ? (
            <p className="text-sm leading-6 text-muted-foreground">
              No research yet. A run uses your configured AI roles (see the
              header pill) and takes a few minutes.
            </p>
          ) : null}
        </CardContent>
      </Card>

      {completed ? (
        <>
          {completed.id !== run?.id ? (
            <p className="text-xs text-muted-foreground">
              Showing the last completed run (#{completed.id}).
            </p>
          ) : null}
          <ResearchView run={completed} deterministic={deterministic} />
        </>
      ) : null}
    </div>
  );
}
