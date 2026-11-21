import type { Metadata } from "next";
import { Suspense } from "react";

import { IpoDetailContent } from "@/components/ipo/detail-content";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "IPO detail",
};

function DetailSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-4 w-32" />
      <div className="space-y-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-9 w-2/3 max-w-md" />
        <Skeleton className="h-4 w-1/2 max-w-sm" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <Skeleton key={index} className="h-24 w-full rounded-lg" />
        ))}
      </div>
      <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <Card>
          <div className="space-y-4 p-5">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-40 w-full" />
          </div>
        </Card>
        <Card>
          <div className="space-y-3 p-5">
            <Skeleton className="h-5 w-32" />
            {Array.from({ length: 8 }).map((_, index) => (
              <Skeleton key={index} className="h-5 w-full" />
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}

export default function IpoDetailPage(props: PageProps<"/ipos/[id]">) {
  return (
    <Suspense fallback={<DetailSkeleton />}>
      <IpoDetailContent
        params={props.params}
        searchParams={props.searchParams}
      />
    </Suspense>
  );
}
