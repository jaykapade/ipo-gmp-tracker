import Link from "next/link";
import { Suspense } from "react";

import { AiStatus } from "@/components/shell/ai-status";
import { SiteNav, SiteNavFallback } from "@/components/shell/site-nav";
import { DailyEmail } from "@/components/shell/daily-email";
import { UserMenu } from "@/components/shell/user-menu";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-dvh flex-col">
      <header className="sticky top-0 z-30 border-b border-border/80 bg-background/80 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="grid size-8 place-items-center rounded-lg bg-primary text-sm font-bold text-primary-foreground">
              IC
            </span>
            <span className="flex flex-col leading-tight">
              <span className="text-sm font-semibold tracking-tight">
                IPO Checker
              </span>
              <span className="text-[11px] text-muted-foreground">
                Indian IPO research
              </span>
            </span>
          </Link>

          <div className="flex items-center gap-3">
            <AiStatus />
            <Suspense fallback={<SiteNavFallback />}>
              <SiteNav />
            </Suspense>
            <Suspense fallback={null}>
              <UserMenu />
            </Suspense>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10">
        {children}
      </main>

      <footer className="border-t border-border/80">
        <div className="mx-auto flex w-full max-w-6xl flex-col gap-2 px-4 py-6 text-xs leading-5 text-muted-foreground sm:px-6">
          <div className="mb-3 border-b border-border/80 pb-5">
            <Suspense fallback={null}>
              <DailyEmail />
            </Suspense>
          </div>
          <p>
            Grey-market premium is unofficial, speculative and can vanish
            before listing. This dashboard is for personal research and is{" "}
            <strong className="font-semibold text-foreground">
              not investment advice
            </strong>
            . Always verify with the official RHP and NSE/BSE filings.
          </p>
          <p>
            Filters and scores are rule-based. AI research is optional, cites
            its sources and is shown beside — never instead of — the
            deterministic score.
          </p>
        </div>
      </footer>
    </div>
  );
}
