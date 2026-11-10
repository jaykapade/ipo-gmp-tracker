/**
 * Small read-only client for the IPO Checker FastAPI service.
 *
 * Requests run in Server Components unless noted. Next.js does not cache
 * `fetch` by default, so pages always render the current shortlist. Callers
 * wrap the async components in `<Suspense>` so Cache Components can prerender
 * the static shell.
 */

import type {
  HealthResponse,
  IPODetail,
  IPOPage,
  ReportInfo,
} from "@/lib/types";

const configuredBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const API_BASE_URL = configuredBaseUrl.replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;

  constructor(
    message: string,
    status: number,
    path: string,
    options?: ErrorOptions,
  ) {
    super(message, options);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
  }
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit & { next?: { revalidate?: number } },
): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...init?.headers,
      },
    });
  } catch (error) {
    throw new ApiError(
      `Could not reach the IPO Checker API at ${API_BASE_URL}.`,
      0,
      path,
      { cause: error },
    );
  }

  if (!response.ok) {
    throw new ApiError(
      `API request failed with status ${response.status}.`,
      response.status,
      path,
    );
  }

  return (await response.json()) as T;
}

export const IPO_SORT_FIELDS = [
  "name",
  "gmp_percent",
  "close_date",
  "subscription",
  "pe",
  "issue_price",
  "updated_at",
] as const;

export type IpoSortField = (typeof IPO_SORT_FIELDS)[number];
export type SortOrder = "asc" | "desc";

/** Human labels used by the dashboard's sort summary. */
export const API_SORT_LABEL: Record<IpoSortField, string> = {
  name: "company name",
  gmp_percent: "latest GMP",
  close_date: "close date",
  subscription: "subscription",
  pe: "P/E",
  issue_price: "issue price",
  updated_at: "latest GMP update",
};

export interface ListIposOptions {
  status?: string | null;
  minGmpPercent?: number | null;
  q?: string | null;
  sort?: IpoSortField;
  order?: SortOrder;
  limit?: number;
  offset?: number;
}

export const api = {
  health(): Promise<HealthResponse> {
    return apiFetch<HealthResponse>("/api/health");
  },

  listIpos(options: ListIposOptions = {}): Promise<IPOPage> {
    const params = new URLSearchParams();
    const {
      status,
      minGmpPercent,
      q,
      sort = "name",
      order = "asc",
      limit = 100,
      offset = 0,
    } = options;

    if (status) params.set("status", status);
    if (minGmpPercent != null) {
      params.set("min_gmp", String(minGmpPercent));
    }
    if (q?.trim()) params.set("q", q.trim());
    params.set("sort", sort);
    params.set("order", order);
    params.set("limit", String(limit));
    params.set("offset", String(offset));

    return apiFetch<IPOPage>(`/api/ipos?${params.toString()}`);
  },

  getIpo(id: number | string): Promise<IPODetail> {
    return apiFetch<IPODetail>(`/api/ipos/${encodeURIComponent(String(id))}`);
  },

  listReports(): Promise<ReportInfo[]> {
    return apiFetch<ReportInfo[]>("/api/reports");
  },

  reportDownloadUrl(filename: string): string {
    return `${API_BASE_URL}/api/reports/${encodeURIComponent(filename)}`;
  },

  /**
   * Stream a chat answer as Server-Sent Events. Returns an async iterator of
   * raw SSE lines; callers parse them into `{ type, data }` events. Intended
   * for Client Components only (SSE requires the browser fetch/ReadableStream).
   *
   * Yields:
   *   - { type: "thinking", data }
   *   - { type: "tool_call", data }
   *   - { type: "tool_result", data }
   *   - { type: "content", data: { delta } }
   *   - { type: "done", data }
   *   - { type: "error", data }
   */
  chat: async function* (
    message: string,
    conversationId?: string | null,
  ): AsyncGenerator<{ type: string; data: unknown }, void, unknown> {
    const params = new URLSearchParams();
    if (conversationId?.trim()) params.set("conversation_id", conversationId.trim());

    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message, conversation_id: conversationId ?? undefined }),
    });

    if (!response.ok || !response.body) {
      throw new ApiError(
        `Chat request failed with status ${response.status}.`,
        response.status,
        "/api/chat",
      );
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let eventIndex: number;
        while ((eventIndex = buffer.indexOf("\n\n")) >= 0) {
          const block = buffer.slice(0, eventIndex);
          buffer = buffer.slice(eventIndex + 2);

          const lines = block.split("\n");
          let eventType: string | null = null;
          const dataLines: string[] = [];
          for (const line of lines) {
            if (line.startsWith("event:")) {
              eventType = line.slice("event:".length).trim();
            } else if (line.startsWith("data:")) {
              dataLines.push(line.slice("data:".length).trim());
            }
          }

          if (eventType == null || dataLines.length === 0) continue;

          const payload = dataLines.join("\n");
          let parsed: unknown;
          try {
            parsed = JSON.parse(payload);
          } catch {
            parsed = { raw: payload };
          }

          yield { type: eventType, data: parsed };
        }
      }

      // Flush any trailing data without a final blank line.
      if (buffer.trim()) {
        const lines = buffer.split("\n");
        let eventType: string | null = null;
        const dataLines: string[] = [];
        for (const line of lines) {
          if (line.startsWith("event:")) {
            eventType = line.slice("event:".length).trim();
          } else if (line.startsWith("data:")) {
            dataLines.push(line.slice("data:".length).trim());
          }
        }
        if (eventType != null && dataLines.length > 0) {
          const payload = dataLines.join("\n");
          let parsed: unknown;
          try {
            parsed = JSON.parse(payload);
          } catch {
            parsed = { raw: payload };
          }
          yield { type: eventType, data: parsed };
        }
      }
    } finally {
      reader.releaseLock();
    }
  },
};
