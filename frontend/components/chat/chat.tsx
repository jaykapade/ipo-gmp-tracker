"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api, ApiError } from "@/lib/api";
import type { ChatMessage } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";

export interface ChatProps {
  initialConversationId?: string | null;
  /** Clickable starter questions shown before the first message. */
  suggestions?: string[];
}

function formatTimestamp(value: string | undefined): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderCitation(citation: unknown): ReactNode {
  if (citation == null || typeof citation !== "object") return null;
  const record = citation as Record<string, unknown>;
  const ipoId = record["ipo_id"];
  const name = record["name"] ?? record["label"] ?? "this IPO";
  const type = record["type"];

  if (type === "ipo_detail" || type === "gmp_history" || type === "analysis") {
    if (ipoId != null) {
      return (
        <a
          href={`/ipos/${String(ipoId)}`}
          className="text-sm font-medium text-primary underline-offset-4 hover:text-primary hover:underline"
        >
          {String(name)}
        </a>
      );
    }
  }
  return <span className="text-xs text-muted-foreground">{String(name)}</span>;
}

function ChatMessage({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={`flex gap-3 ${
        isUser ? "flex-row-reverse" : ""
      }`}
    >
      <div className="flex flex-col gap-1.5">
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
          {isUser ? "You" : "IPO Checker"}
        </span>
        <div className={`max-w-[85%] ${
          isUser
            ? "ml-auto rounded-xl bg-primary text-primary-foreground p-3"
            : "rounded-xl border border-border bg-card p-3"
        }`}>
          <div className="prose prose-sm text-sm leading-6 max-w-none">
            {message.content.split("\n").map((paragraph, index) => (
              <p key={index} className="mb-2 last:mb-0">
                {paragraph}
              </p>
            ))}
          </div>
          {(message.citations?.length ?? 0) > 0 && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {message.citations?.map((citation, index) => (
                <span key={index} className="text-[10px] text-muted-foreground">
                  {renderCitation(citation)}
                </span>
              ))}
            </div>
          )}
          <p className="mt-2 text-[10px] text-muted-foreground">
            {formatTimestamp(message.createdAt)}
            {message.dataAsOf ? ` · data as of ${message.dataAsOf}` : ""}
          </p>
        </div>
      </div>
    </div>
  );
}

function StreamPlaceholder() {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
        IPO Checker
      </span>
      <div className="rounded-xl border border-border bg-card p-3 w-3/4 animate-pulse">
        <Skeleton className="h-4 w-1/2 mb-2" />
        <Skeleton className="h-4 w-3/4" />
      </div>
    </div>
  );
}

export function Chat({ initialConversationId, suggestions = [] }: ChatProps) {
  const [conversationId, setConversationId] = useState<string | null>(
    initialConversationId ?? null,
  );
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const stopStreaming = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setStreaming(false);
    setError(null);
  }, []);

  useEffect(() => {
    return () => {
      stopStreaming();
    };
  }, [stopStreaming]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const message = inputValue.trim();
    if (!message || streaming) return;

    setError(null);
    const optimisticMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: "user",
      content: message,
      createdAt: new Date().toISOString(),
    };

    setMessages((previous) => [...previous, optimisticMessage]);
    setInputValue("");
    setStreaming(true);

    const assistantId = `msg-${Date.now() + 1}`;
    setMessages((previous) => [
      ...previous,
      {
        id: assistantId,
        role: "assistant",
        content: "",
        createdAt: new Date().toISOString(),
      },
    ]);

    let currentDataAsOf: string | null = null;
    let currentCitations: ChatMessage["citations"] = [];

    try {
      abortRef.current = new AbortController();
      const stream = api.chat(message, conversationId);

      for await (const event of stream) {
        if (event.type === "thinking") {
          continue;
        }

        if (event.type === "error") {
          const detail = (event.data as Record<string, unknown>)?.message ??
            "Chat failed.";
          setError(String(detail));
          break;
        }

        if (event.type === "content") {
          const delta = (event.data as Record<string, unknown>)?.delta ?? "";
          setMessages((previous) =>
            previous.map((item) =>
              item.id === assistantId
                ? { ...item, content: item.content + String(delta) }
                : item,
            ),
          );
          continue;
        }

        if (event.type === "done") {
          const done = event.data as Record<string, unknown>;
          const rawDataAsOf = done?.data_as_of;
          currentDataAsOf = rawDataAsOf == null ? null : String(rawDataAsOf);
          const citations = done?.citations ?? [];
          if (Array.isArray(citations)) {
            currentCitations = citations as ChatMessage["citations"];
          }
          setConversationId(String(done?.conversation_id ?? conversationId ?? ""));
          break;
        }
      }
    } catch (caught) {
      if (caught instanceof Error && caught.name === "AbortError") {
        setStreaming(false);
        return;
      }
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Could not reach the chat backend.",
      );
    } finally {
      setStreaming(false);
      abortRef.current = null;

      setMessages((previous) =>
        previous.map((item) =>
          item.id === assistantId
            ? {
                ...item,
                dataAsOf: currentDataAsOf,
                citations: currentCitations,
                refusal:
                  (currentCitations?.length ?? 0) === 0 &&
                  !currentDataAsOf &&
                  item.content.includes("couldn't find"),
              }
            : item,
        ),
      );
    }
  };

  if (error) {
    return (
      <Card>
        <CardContent className="p-5">
          <Badge tone="danger">Error</Badge>
          <p className="mt-2 text-sm leading-6">{error}</p>
          <button
            onClick={() => {
              setError(null);
              setStreaming(false);
            }}
            className="mt-3 rounded-md border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          >
            Try again
          </button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex-1 min-h-[300px] overflow-y-auto space-y-4 px-4 sm:px-6">
        {messages.length === 0 ? (
          <div className="space-y-4 py-6">
            <EmptyState
              title="Ask about any tracked IPO"
              description="Name a company and get a grounded answer from the latest scraped data, its GMP history and stored analysis."
            />
            {suggestions.length > 0 ? (
              <div className="flex flex-wrap justify-center gap-2">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    onClick={() => setInputValue(suggestion)}
                    className="rounded-full border border-border bg-background px-3 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:border-primary hover:text-foreground"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}
            {streaming && <StreamPlaceholder />}
          </>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 px-4 pb-4 sm:px-6">
        <input
          autoFocus
          disabled={streaming}
          value={inputValue}
          onChange={(event) => setInputValue(event.target.value)}
          placeholder="Ask about an IPO by name…"
          className="flex-1 h-9 rounded-md border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary disabled:opacity-60 disabled:pointer-events-none"
        />
        <button
          type="submit"
          disabled={streaming || !inputValue.trim()}
          className="h-9 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition-opacity disabled:opacity-50 disabled:pointer-events-none hover:opacity-90"
        >
          Send
        </button>
        {streaming && (
          <button
            type="button"
            onClick={stopStreaming}
            className="h-9 rounded-md border border-border px-3 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
            aria-label="Stop streaming"
          >
            Stop
          </button>
        )}
      </form>

      {error ? null : null}
    </div>
  );
}
