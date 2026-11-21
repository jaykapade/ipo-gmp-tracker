/**
 * Calls to the backend's token-protected routes, from the Next server only.
 * The token proves a request came through this server (which checked sign-in).
 */

import "server-only";

import { API_BASE_URL } from "@/lib/api";

export async function backend(path: string, init?: RequestInit): Promise<Response | null> {
  const token = process.env.API_TOKEN;
  try {
    return await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-API-Token": token } : {}),
      },
      cache: "no-store",
    });
  } catch {
    return null;
  }
}

/** Whether `email` gets the daily email; null when the backend is unreachable. */
export async function isSubscribed(email: string): Promise<boolean | null> {
  const response = await backend(`/api/subscribers?email=${encodeURIComponent(email)}`);
  if (!response?.ok) return null;
  return ((await response.json()) as { subscribed: boolean }).subscribed;
}
