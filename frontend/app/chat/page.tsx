import type { Metadata } from "next";

import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";

export const metadata: Metadata = {
  title: "Chat",
};

const EXAMPLES = [
  "Which active IPOs have GMP above 30% and close this week?",
  "Compare the valuation and GMP trend of the top two SME IPOs.",
  "What are the main risks in the RHP of the highest-GMP IPO?",
  "Why did this IPO make the shortlist, and what data is missing?",
];

const GROUNDING = [
  "Questions are answered from whitelisted data tools, never raw SQL.",
  "Every answer will show the data timestamp and inline citations.",
  "Missing data is called out instead of guessed.",
  "Local providers are the default; cloud calls require explicit opt-in.",
];

export default function ChatPage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Assistant"
        title="Talk to the current shortlist"
        description="A grounded chat assistant for the IPOs already in the database. The UI is scaffolded; the streaming chat backend and provider layer are the next milestone."
      />

      <Card>
        <CardContent className="space-y-7">
          <div className="rounded-xl border border-dashed border-border bg-muted/40 px-5 py-10 text-center">
            <Badge tone="warning">Planned · P1</Badge>
            <p className="mt-3 text-sm font-semibold">
              Chat is not wired up yet
            </p>
            <p className="mx-auto mt-1 max-w-xl text-sm leading-6 text-muted-foreground">
              The backend has the data endpoints and deterministic analysis.
              Wiring the provider-agnostic AI layer and streaming{" "}
              <code className="font-mono text-xs">POST /api/chat</code> is the
              next step, so this page intentionally does not fake an answer.
            </p>
          </div>

          <div className="grid gap-8 sm:grid-cols-2">
            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Example questions
              </h2>
              <ul className="mt-3 space-y-2.5 text-sm leading-6">
                {EXAMPLES.map((example) => (
                  <li key={example} className="flex gap-2">
                    <span aria-hidden="true" className="text-primary">
                      →
                    </span>
                    <span>{example}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section>
              <h2 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                How it will stay grounded
              </h2>
              <ul className="mt-3 space-y-2.5 text-sm leading-6">
                {GROUNDING.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span aria-hidden="true" className="text-primary">
                      ✓
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
