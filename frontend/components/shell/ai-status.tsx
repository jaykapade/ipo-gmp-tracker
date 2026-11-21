"use client";

import { useEffect, useState } from "react";

import { API_BASE_URL } from "@/lib/api";
import type { AIHealth, HealthResponse } from "@/lib/types";
import { cn } from "@/lib/utils";

type State =
  | { kind: "loading" }
  | { kind: "offline" }
  | { kind: "ready"; ai: AIHealth };

function providerLabel(ai: AIHealth): string {
  switch (ai.provider) {
    case "claude-code":
      return "Claude · subscription";
    case "anthropic":
      return "Claude · API";
    case "ollama":
      return "Ollama · local";
    default:
      return ai.provider;
  }
}

/**
 * Header pill showing which AI provider the backend is using.
 *
 * Runs in the browser once per page load (the layout persists across
 * navigations), so the health probe is not repeated on every route change
 * and never baked into a prerendered shell.
 */
export function AiStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${API_BASE_URL}/api/health`, { signal: controller.signal })
      .then((response) =>
        response.ok ? (response.json() as Promise<HealthResponse>) : null,
      )
      .then((health) =>
        setState(health ? { kind: "ready", ai: health.ai } : { kind: "offline" }),
      )
      .catch((error: unknown) => {
        if ((error as Error).name !== "AbortError") setState({ kind: "offline" });
      });
    return () => controller.abort();
  }, []);

  let dot = "bg-muted-foreground/40";
  let label = "Checking AI…";
  let title = "Checking the backend's AI status";

  if (state.kind === "offline") {
    dot = "bg-danger";
    label = "API offline";
    title = `Backend not reachable at ${API_BASE_URL}`;
  } else if (state.kind === "ready") {
    const { ai } = state;
    if (!ai.enabled) {
      label = "AI off";
      title = "Deterministic mode (LLM_ENABLED=false)";
    } else {
      dot = ai.available ? "bg-success" : "bg-warning";
      label = providerLabel(ai);
      const roles = Object.entries(ai.roles ?? {})
        .filter(([, role]) => role.enabled)
        .map(([name, role]) => `${name}: ${role.model}`)
        .join("\n");
      title = `${ai.detail}${roles ? `\n\n${roles}` : ""}`;
    }
  }

  return (
    <span
      title={title}
      className="hidden items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs font-medium text-muted-foreground sm:inline-flex"
    >
      <span aria-hidden="true" className={cn("size-2 rounded-full", dot)} />
      {label}
    </span>
  );
}
