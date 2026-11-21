"""Claude subscription adapter via the headless ``claude`` CLI.

A Claude Pro/Max subscription cannot authenticate the Messages API (that needs
a separately billed API key). The supported route for a subscription is the
Claude Code CLI in print mode, so this adapter runs one ``claude -p`` process
per generation:

* tools, project settings, MCP servers and session persistence are all
  disabled, so the call is a pure completion;
* the transcript is piped on stdin (no Windows argv-length limits);
* ``ANTHROPIC_API_KEY`` / ``ANTHROPIC_AUTH_TOKEN`` are stripped from the child
  environment so the CLI bills the logged-in subscription, never the API.

This mode is for **personal use only**. For a multi-user or commercial
deployment switch ``LLM_PROVIDER=anthropic`` and set ``LLM_API_KEY`` — model
ids and callers stay identical.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NoReturn

from src.llm.base import (
    EmbeddingResponse,
    LLMMessage,
    LLMProvider,
    LLMResponse,
    ProviderCapabilities,
    ProviderHealth,
    ProviderNotConfiguredError,
    ProviderUnavailableError,
    TokenUsage,
    validate_against_schema,
)

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)

DEFAULT_BINARY = "claude"
# Structured output runs through an internal tool call, which costs a turn.
_MAX_TURNS_PLAIN = 1
_MAX_TURNS_SCHEMA = 3
_STRIPPED_ENV = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
WEB_TOOLS = "WebSearch,WebFetch"
DEFAULT_WEB_MAX_TURNS = 30
_AUTH_HINTS = ("not logged in", "please run /login", "invalid api key", "oauth")

Runner = Callable[..., Any]

_announced = False
_announce_lock = threading.Lock()
_semaphores: dict[int, threading.BoundedSemaphore] = {}
_semaphores_lock = threading.Lock()


def _concurrency_gate(limit: int) -> threading.BoundedSemaphore:
    """Process-wide semaphore shared by every claude-code provider instance."""

    limit = max(1, limit)
    with _semaphores_lock:
        gate = _semaphores.get(limit)
        if gate is None:
            gate = threading.BoundedSemaphore(limit)
            _semaphores[limit] = gate
        return gate


def _announce_personal_mode() -> None:
    global _announced
    with _announce_lock:
        if _announced:
            return
        _announced = True
    logger.info(
        "claude-code provider: subscription mode — personal use only; "
        "use LLM_PROVIDER=anthropic with LLM_API_KEY for multi-user deployments"
    )


def render_transcript(messages: list[LLMMessage]) -> str:
    """Flatten non-system messages into one prompt for print mode.

    A single user turn is passed through verbatim; multi-turn history is
    labelled so the model can tell the speakers apart.
    """

    turns = [message for message in messages if message.role != "system"]
    if len(turns) == 1 and turns[0].role == "user":
        return turns[0].content
    return "\n\n".join(
        f"{'User' if message.role == 'user' else 'Assistant'}: {message.content}"
        for message in turns
    )


class ClaudeCodeProvider(LLMProvider):
    """Generate through ``claude -p`` using the logged-in subscription."""

    def __init__(
        self,
        *,
        model: str,
        binary: str | None = None,
        timeout: float = 120.0,
        max_concurrency: int = 2,
        runner: Runner | None = None,
        web_tools: bool = False,
        max_turns: int | None = None,
    ) -> None:
        self.name = "claude-code"
        self.model = model
        self.is_cloud = True
        self.binary = (binary or DEFAULT_BINARY).strip() or DEFAULT_BINARY
        self.timeout = timeout
        self.max_concurrency = max(1, max_concurrency)
        # Web mode: the CLI may search/fetch pages (auto-approved, no other
        # tools) and needs many turns for the tool round-trips.
        self.web_tools = web_tools
        self.max_turns = max_turns
        self._runner: Runner = runner if runner is not None else subprocess.run
        self._injected_runner = runner is not None
        _announce_personal_mode()

    # --- Process plumbing --------------------------------------------------

    def _resolve_binary(self) -> str:
        if self._injected_runner:
            return self.binary
        resolved = shutil.which(self.binary)
        if resolved is None:
            raise ProviderNotConfiguredError(
                f"claude-code: CLI {self.binary!r} not found on PATH; install "
                "Claude Code or set LLM_BASE_URL to the claude executable path"
            )
        return resolved

    @staticmethod
    def _child_env() -> dict[str, str]:
        env = dict(os.environ)
        for name in _STRIPPED_ENV:
            env.pop(name, None)
        return env

    def _run(self, args: list[str], *, stdin: str | None) -> Any:
        command = [self._resolve_binary(), *args]
        try:
            with _concurrency_gate(self.max_concurrency):
                return self._runner(
                    command,
                    input=stdin,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=self.timeout,
                    env=self._child_env(),
                    check=False,
                )
        except subprocess.TimeoutExpired as exc:
            raise ProviderUnavailableError(
                f"claude-code: timed out after {self.timeout:.0f}s"
            ) from exc
        except OSError as exc:
            raise ProviderUnavailableError(
                f"claude-code: could not start CLI: {exc}"
            ) from exc

    @staticmethod
    def _raise_for_failure(detail: str) -> NoReturn:
        lowered = detail.lower()
        if any(hint in lowered for hint in _AUTH_HINTS):
            raise ProviderNotConfiguredError(
                f"claude-code: not authenticated ({detail[:200]}); "
                "run `claude auth login` with your Claude subscription"
            )
        raise ProviderUnavailableError(f"claude-code: {detail[:300]}")

    # --- Contract ----------------------------------------------------------

    def generate(
        self,
        messages: list[LLMMessage],
        *,
        response_schema: type[BaseModel] | None = None,
        temperature: float | None = None,  # noqa: ARG002 - CLI exposes no knob
        max_tokens: int | None = None,  # noqa: ARG002 - CLI exposes no knob
    ) -> LLMResponse:
        system = "\n\n".join(
            message.content for message in messages if message.role == "system"
        )
        if self.web_tools:
            turns = self.max_turns or DEFAULT_WEB_MAX_TURNS
        elif self.max_turns:
            turns = self.max_turns
        else:
            turns = _MAX_TURNS_SCHEMA if response_schema else _MAX_TURNS_PLAIN
        tool_args = (
            ["--tools", WEB_TOOLS, "--allowedTools", WEB_TOOLS]
            if self.web_tools
            else ["--tools", ""]
        )
        args = [
            "-p",
            "--output-format",
            "json",
            "--model",
            self.model,
            *tool_args,
            "--max-turns",
            str(turns),
            "--no-session-persistence",
            "--setting-sources",
            "",
            "--strict-mcp-config",
        ]
        if system:
            args += ["--system-prompt", system]
        if response_schema is not None:
            args += [
                "--json-schema",
                json.dumps(response_schema.model_json_schema(), separators=(",", ":")),
            ]

        started = time.monotonic()
        completed = self._run(args, stdin=render_transcript(messages))
        stdout = (completed.stdout or "").strip()

        try:
            body = json.loads(stdout) if stdout else None
        except json.JSONDecodeError:
            body = None

        if not isinstance(body, dict):
            detail = (completed.stderr or stdout or "no output").strip()
            self._raise_for_failure(
                f"exit {completed.returncode}: {detail}"
                if completed.returncode
                else f"unparseable output: {detail}"
            )

        if body.get("is_error") or completed.returncode != 0:
            detail = str(
                body.get("result")
                or body.get("subtype")
                or completed.stderr
                or f"exit {completed.returncode}"
            ).strip()
            self._raise_for_failure(detail)

        structured = body.get("structured_output")
        if response_schema is not None and structured is not None:
            text = json.dumps(structured)
        else:
            text = str(body.get("result") or "")

        parsed = None
        if response_schema is not None:
            # Same shared gate as every other provider, even with --json-schema.
            parsed = validate_against_schema(text, response_schema)

        usage_raw = body.get("usage") or {}
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            usage=TokenUsage(
                input_tokens=usage_raw.get("input_tokens"),
                output_tokens=usage_raw.get("output_tokens"),
            ),
            finish_reason=body.get("stop_reason"),
            latency_seconds=time.monotonic() - started,
            parsed=parsed,
        )

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        raise ProviderNotConfiguredError(
            "claude-code has no embeddings; set LLM_EMBED_PROVIDER "
            "(e.g. ollama with qwen3-embedding:0.6b)"
        )

    def health(self, timeout: float | None = None) -> ProviderHealth:
        """Check the CLI login with ``claude auth status`` (free, no tokens)."""

        try:
            completed = self._runner(
                [self._resolve_binary(), "auth", "status"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout if timeout is not None else 10.0,
                env=self._child_env(),
                check=False,
            )
        except ProviderNotConfiguredError as exc:
            return ProviderHealth(ok=False, detail=str(exc))
        except (subprocess.TimeoutExpired, OSError) as exc:
            return ProviderHealth(ok=False, detail=f"claude-code: {exc}")

        try:
            status = json.loads(completed.stdout or "")
        except json.JSONDecodeError:
            return ProviderHealth(
                ok=False,
                detail=f"claude-code: unreadable auth status "
                f"({(completed.stderr or completed.stdout or '').strip()[:120]})",
            )

        if not status.get("loggedIn"):
            return ProviderHealth(
                ok=False, detail="claude-code: not logged in; run `claude auth login`"
            )
        method = status.get("authMethod") or "unknown"
        if method != "claude.ai":
            return ProviderHealth(
                ok=True,
                detail=f"claude-code: logged in via {method} "
                "(not a subscription login — usage may be API-billed)",
            )
        return ProviderHealth(
            ok=True, detail="claude-code: logged in via claude.ai subscription"
        )

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            json_mode=True,
            tools=self.web_tools,
            web_research=True,
            embeddings=False,
            vision=False,
            streaming=False,
            context_window=200_000,
        )


__all__ = ["DEFAULT_BINARY", "ClaudeCodeProvider", "render_transcript"]
