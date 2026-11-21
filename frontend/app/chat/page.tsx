import type { Metadata } from "next";
import { Suspense } from "react";

import { currentEmail } from "@/auth";
import { Chat } from "@/components/chat/chat";
import { SignInButton } from "@/components/shell/user-menu";
import { PageHeader } from "@/components/shell/page-header";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { api } from "@/lib/api";

const GROUNDING = [
  "Answers come from whitelisted data lookups, never raw SQL.",
  "Every answer shows the data timestamp and links to the IPO it used.",
  "Missing data is called out instead of guessed.",
  "With AI on, the analyst role phrases the answer; with AI off, a deterministic template does.",
];

export const metadata: Metadata = {
  title: "Chat",
};

/** Starter questions built from the IPOs currently in the database. */
async function ChatWithSuggestions() {
  if (!(await currentEmail())) {
    return (
      <div className="space-y-3 px-4 pb-6 sm:px-6">
        <p className="text-sm leading-6 text-muted-foreground">
          Chat answers can use the AI provider, so it is for signed-in users.
        </p>
        <SignInButton />
      </div>
    );
  }

  const page = await api
    .listIpos({ sort: "gmp_percent", order: "desc", limit: 4 })
    .catch(() => null);
  const names = page?.items.map((ipo) => ipo.name) ?? [];

  const suggestions = [
    ...names.slice(0, 2).map((name) => `Tell me about ${name}`),
    ...(names[2] ? [`What is the GMP trend for ${names[2]}?`] : []),
    ...(names[3] ? [`Why did ${names[3]} get its score?`] : []),
  ];

  return <Chat initialConversationId={null} suggestions={suggestions} />;
}

export default function ChatPage() {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Assistant"
        title="Ask about the tracked IPOs"
        description="Ask about an IPO by name and get an answer streamed from the latest scraped data, with citations to the IPO, its GMP history and any stored analysis."
      />

      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-8">
          <Card>
            <CardHeader
              title="Conversation"
              description="Streamed, grounded answers."
            />
            <CardContent className="p-0 pt-4">
              <Suspense fallback={null}>
                <ChatWithSuggestions />
              </Suspense>
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <Card>
            <CardHeader title="How it stays grounded" />
            <CardContent>
              <ul className="space-y-2.5 text-sm leading-6">
                {GROUNDING.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span aria-hidden="true" className="text-primary">
                      ✓
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader title="Want deeper research?" />
            <CardContent>
              <p className="text-sm leading-6 text-muted-foreground">
                Chat answers from stored data only. For cited web research,
                four analyst perspectives and an independent verifier, open an
                IPO and use its <strong className="text-foreground">AI research</strong>{" "}
                tab.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
