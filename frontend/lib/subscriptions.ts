"use server";

/**
 * Server Actions for the daily email.
 *
 * Signed-in users subscribe their Google-verified email (no confirmation
 * email needed); the unsubscribe link in each email works without signing in.
 * Next.js rejects Server Action calls whose Origin does not match the host (CSRF).
 */

import { currentEmail } from "@/auth";
import { backend } from "@/lib/backend";

export type FormResult = { ok: boolean; message: string; subscribed?: boolean } | null;

export async function setDailyEmail(
  _previous: FormResult,
  formData: FormData,
): Promise<FormResult> {
  const email = await currentEmail();
  if (!email) return { ok: false, message: "Sign in first." };
  const subscribed = formData.get("subscribed") === "true";

  const response = await backend("/api/subscribers", {
    method: "PUT",
    body: JSON.stringify({ email, subscribed }),
  });
  if (!response?.ok) return { ok: false, message: "Could not save. Try again later." };
  return {
    ok: true,
    subscribed,
    message: subscribed ? `Daily email on. It goes to ${email}.` : "Daily email off.",
  };
}

export async function unsubscribeLink(
  _previous: FormResult,
  formData: FormData,
): Promise<FormResult> {
  const token = String(formData.get("token") ?? "");
  if (!/^[\w-]{10,100}$/.test(token)) {
    return { ok: false, message: "This link is not valid." };
  }

  const response = await backend("/api/subscribers/unsubscribe", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
  if (!response) return { ok: false, message: "The service is offline. Try again later." };
  if (response.ok) {
    return { ok: true, message: "You're unsubscribed. No more emails will be sent." };
  }
  return {
    ok: false,
    message:
      response.status === 404 ? "This link is not valid." : "Something went wrong. Try again later.",
  };
}
