import type { Metadata } from "next";
import { Suspense } from "react";

import { DashboardContent } from "@/components/dashboard/dashboard-content";
import { PageHeader } from "@/components/shell/page-header";
import { Card } from "@/components/ui/card";
import { TableSkeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function DashboardPage(props: PageProps<"/">) {
  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Live shortlist"
        title="IPO dashboard"
        description={
          <>
            Active Indian IPOs whose latest grey-market premium meets the{" "}
            <strong className="font-semibold text-foreground">20% minimum</strong>{" "}
            screen. Scores, verdicts and reports stay deterministic — no model is
            involved in filtering.
          </>
        }
      />

      <Suspense
        fallback={
          <Card>
            <TableSkeleton rows={8} />
          </Card>
        }
      >
        <DashboardContent searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
