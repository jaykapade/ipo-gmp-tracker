import type { Metadata } from "next";
import { Suspense } from "react";

import { UnsubscribeForm } from "@/components/shell/subscription-forms";

export const metadata: Metadata = {
  title: "Email subscription",
  robots: { index: false },
};

async function SubscriptionAction({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { action, token } = await searchParams;
  if (action !== "unsubscribe" || typeof token !== "string") {
    return (
      <p className="text-sm text-muted-foreground">
        This link is incomplete. Open it again from the email.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-sm leading-6 text-muted-foreground">
        Unsubscribe to stop the daily IPO email. You can turn it back on from
        the site footer after signing in.
      </p>
      <UnsubscribeForm token={token} />
    </div>
  );
}

export default function SubscriptionPage(props: PageProps<"/subscription">) {
  return (
    <div className="mx-auto max-w-md space-y-4 py-12">
      <h1 className="text-2xl font-semibold tracking-tight">Email subscription</h1>
      <Suspense fallback={null}>
        <SubscriptionAction searchParams={props.searchParams} />
      </Suspense>
    </div>
  );
}
