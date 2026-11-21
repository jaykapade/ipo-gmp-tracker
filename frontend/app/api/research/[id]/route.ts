/**
 * Server-side proxy for AI research.
 *
 * Starting research needs a signed-in user and is token-protected on the
 * backend. The browser must never
 * see `API_TOKEN`, so the client calls this route and the Next server adds the
 * `X-API-Token` header from its own (non-`NEXT_PUBLIC`) environment.
 */

import { auth } from "@/auth";
import { API_BASE_URL } from "@/lib/api";

function backendUrl(id: string): string | null {
  return /^\d+$/.test(id) ? `${API_BASE_URL}/api/ipos/${id}/research` : null;
}

async function relay(response: Response): Promise<Response> {
  const body = await response.text();
  return new Response(body || "null", {
    status: response.status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });
}

function unreachable(): Response {
  return Response.json(
    { detail: `Backend not reachable at ${API_BASE_URL}.` },
    { status: 502 },
  );
}

export async function GET(
  _request: Request,
  ctx: RouteContext<"/api/research/[id]">,
): Promise<Response> {
  const url = backendUrl((await ctx.params).id);
  if (!url) return Response.json({ detail: "Invalid IPO id." }, { status: 400 });
  try {
    return await relay(await fetch(url, { cache: "no-store" }));
  } catch {
    return unreachable();
  }
}

export async function POST(
  request: Request,
  ctx: RouteContext<"/api/research/[id]">,
): Promise<Response> {
  // Block cross-site form posts (CSRF): browsers mark them non-same-origin.
  const site = request.headers.get("sec-fetch-site");
  if (site && site !== "same-origin") {
    return Response.json({ detail: "Cross-site request refused." }, { status: 403 });
  }
  // Research spends AI quota: signed-in users only.
  if (!(await auth())?.user) {
    return Response.json({ detail: "Sign in to run AI research." }, { status: 401 });
  }
  const url = backendUrl((await ctx.params).id);
  if (!url) return Response.json({ detail: "Invalid IPO id." }, { status: 400 });

  const token = process.env.API_TOKEN;
  try {
    return await relay(
      await fetch(url, {
        method: "POST",
        headers: token ? { "X-API-Token": token } : undefined,
        cache: "no-store",
      }),
    );
  } catch {
    return unreachable();
  }
}
