"use client";

import { useActionState } from "react";

import { setDailyEmail, unsubscribeLink, type FormResult } from "@/lib/subscriptions";
import { cn } from "@/lib/utils";

const button =
  "h-9 shrink-0 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50";

function Result({ state }: { state: FormResult }) {
  return (
    <p
      aria-live="polite"
      className={cn("min-h-5 text-xs", state?.ok ? "text-success" : "text-danger")}
    >
      {state?.message}
    </p>
  );
}

/** Footer toggle for a signed-in user's daily email. */
export function DailyEmailToggle({ subscribed }: { subscribed: boolean }) {
  const [state, action, pending] = useActionState(setDailyEmail, null);
  // After a save, the action's result is newer than the server-rendered prop.
  const on = state?.subscribed ?? subscribed;

  return (
    <form action={action} className="flex flex-wrap items-center gap-3">
      <input type="hidden" name="subscribed" value={on ? "false" : "true"} />
      <button type="submit" disabled={pending} className={button}>
        {pending ? "Saving…" : on ? "Turn off" : "Turn on"}
      </button>
      <Result state={state} />
    </form>
  );
}

/**
 * Unsubscribe button for the link in subscriber emails.
 *
 * A button rather than acting on page load: mail scanners open links in
 * emails, and that must not unsubscribe anyone.
 */
export function UnsubscribeForm({ token }: { token: string }) {
  const [state, action, pending] = useActionState(unsubscribeLink, null);

  return (
    <form action={action} className="space-y-3">
      <input type="hidden" name="token" value={token} />
      {state?.ok ? null : (
        <button type="submit" disabled={pending} className={button}>
          {pending ? "Working…" : "Unsubscribe"}
        </button>
      )}
      <Result state={state} />
    </form>
  );
}
