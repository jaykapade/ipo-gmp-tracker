import type { Metadata } from "next";

import { PageHeader } from "@/components/shell/page-header";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

import { Chat } from "@/components/chat/chat";

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

export const metadata: Metadata = {
  title: "Chat",
};

export default function ChatPage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Assistant"
        title="Talk to the current shortlist"
        description={
          <>
            Ask about an IPO by name and get a grounded answer streamed from the
            latest scraped data. Answers cite the dashboard IPO, its GMP history
            and any stored analysis. Missing data is flagged instead of guessed.
          </>
        }
      />

      <div className="grid gap-7 sm:grid-cols-12">
        <div className="sm:col-span-8">
          <Card>
            <CardHeader
              title="Conversation"
              description="Streamed answers from whitelisted data tools."
            />
            <CardContent className="p-0">
              <Chat initialConversationId={null} />
            </CardContent>
          </Card>
        </div>

        <div className="sm:col-span-4 space-y-7">
          <Card>
            <CardContent className="space-y-7">
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
                  How it stays grounded
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
            </CardContent>
          </Card>

          <Card>
            <CardContent className="p-5">
              <Badge tone="info">Data from dashboard</Badge>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Answers reflect whatever IPOs and GMP observations are currently
                in the database. Run a scrape to refresh before asking.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
