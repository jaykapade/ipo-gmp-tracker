/**
 * Server-side proxy for the chat stream; signed-in users only.
 *
 * With AI on, each chat question costs an AI call. This route checks the
 * Google sign-in, then adds `X-API-Token` so the backend knows the request
 * came through here; the browser never sees the token.
 */

import { auth } from "@/auth";
import { API_BASE_URL } from "@/lib/api";

export async function POST(request: Request): Promise<Response> {
  // Block cross-site posts (CSRF): browsers mark them non-same-origin.
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin") {
    return Response.json({ detail: "Cross-site request refused." }, { status: 403 });
  }
  if (!(await auth())?.user) {
    return Response.json({ detail: "Sign in to use chat." }, { status: 401 });
  }

  const token = process.env.API_TOKEN;
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-API-Token": token } : {}),
      },
      body: await request.text(),
      cache: "no-store",
    });
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") ?? "text/event-stream",
        "Cache-Control": "no-cache",
      },
    });
  } catch {
    return Response.json(
      { detail: `Backend not reachable at ${API_BASE_URL}.` },
      { status: 502 },
    );
  }
}
