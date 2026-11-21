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
        eyebrow="Live tracker"
        title="IPO dashboard"
        description={
          <>
            Every IPO currently tracked, with its latest grey-market premium.
            Filter by board, GMP threshold or research status; open an IPO to
            see its history, the rule-based score and{" "}
            <strong className="font-semibold text-foreground">
              AI research
            </strong>
            . Filtering and scoring never involve a model.
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
