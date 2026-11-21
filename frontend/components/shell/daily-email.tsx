import { currentEmail } from "@/auth";
import { DailyEmailToggle } from "@/components/shell/subscription-forms";
import { SignInButton } from "@/components/shell/user-menu";
import { isSubscribed } from "@/lib/backend";

/** Footer: the daily IPO email for the signed-in user. Render inside Suspense. */
export async function DailyEmail() {
  const email = await currentEmail();
  const subscribed = email ? await isSubscribed(email) : null;

  return (
    <div className="space-y-1.5">
      <p className="text-sm font-medium text-foreground">Daily IPO email</p>
      <p>Open IPOs and their latest GMP, once a day. Unsubscribe from any email.</p>
      {!email ? (
        <SignInButton label="Sign in with Google to subscribe" />
      ) : subscribed === null ? (
        <p>The service is offline. Try again later.</p>
      ) : (
        <DailyEmailToggle subscribed={subscribed} />
      )}
    </div>
  );
}
