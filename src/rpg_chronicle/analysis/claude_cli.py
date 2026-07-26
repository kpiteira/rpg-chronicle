"""Subscription-mediated transport: reach Claude through the Claude Code CLI.

This is the one module in the package permitted to name a vendor, and it is the only
thing that would be replaced by an API-key or gateway backend. It knows nothing about
transcripts, scenes, windows, or the attention budget.

Why the CLI rather than an API key: the operator already pays for a Claude subscription
and the repository already invokes a headless session this way in
`scripts/validate-goal.sh`, so this is an established mechanism rather than a new one.
The cost is that a run is denominated in tokens and wall time rather than in currency,
and that a third party cannot reproduce it from the public repository without their own
subscription. That trade-off is in tension with D-001 and is raised as a proposed
decision entry rather than settled here.

The invocation is deliberately stripped down. A default headless session carries its
own system prompt, tool definitions, project settings, and MCP configuration -- around
35,000 tokens before any transcript is added, which would swamp the cost figure this
package exists to measure. Replacing the system prompt and disabling tools brings the
fixed overhead to a couple of hundred tokens.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time

from .backend import (
    BackendResponseError,
    BackendUnavailableError,
    ModelRequest,
    ModelResponse,
    TokenUsage,
)

DEFAULT_MODEL = "claude-sonnet-5"
DEFAULT_EXECUTABLE = "claude"
DEFAULT_TIMEOUT_SECONDS = 900


class ClaudeCliBackend:
    """Reaches a Claude model through a headless `claude -p` process.

    The operator's subscription is the credential, held by the CLI itself. Nothing in
    this class reads, stores, or emits credential material; an unauthenticated CLI
    surfaces as an unavailable backend with the CLI's own message.
    """

    name = "claude-code-cli"

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        executable: str = DEFAULT_EXECUTABLE,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.model = model
        self.executable = executable
        self.timeout_seconds = timeout_seconds

    def preflight(self) -> None:
        """Fail before any transcript is sent if the CLI is not usable.

        Checking up front matters because the pipeline persists analysis only after a
        provider returns. A backend that fails on its first request rather than at
        preflight would still leave no partial artifact, but it would have spent the
        operator's wall time discovering something knowable in a millisecond.
        """
        if shutil.which(self.executable) is None:
            raise BackendUnavailableError(
                f"backend {self.name!r} needs the {self.executable!r} executable on PATH, "
                "and it was not found. This backend is subscription-mediated: install "
                "the Claude Code CLI and authenticate it interactively. No API key is "
                "read from the repository."
            )

    def _argv(self, request: ModelRequest) -> list[str]:
        return [
            self.executable,
            "-p",
            "--model",
            self.model,
            "--output-format",
            "json",
            # Replace the agent system prompt rather than appending to it: the default
            # one describes a coding agent with a filesystem, which is neither true nor
            # free here.
            "--system-prompt",
            request.system,
            # This backend answers one question with text. Every capability below is
            # both useless and billed as input tokens on every request.
            "--tools",
            "",
            "--disable-slash-commands",
            "--strict-mcp-config",
            "--setting-sources",
            "",
            "--no-session-persistence",
        ]

    def complete(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        try:
            completed = subprocess.run(
                self._argv(request),
                input=request.user,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as error:
            raise BackendUnavailableError(
                f"backend {self.name!r} could not run {self.executable!r}: {error}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise BackendResponseError(
                f"backend {self.name!r} timed out after {self.timeout_seconds}s. "
                "A single request carrying several hours of transcript can exceed the "
                "default; raise timeout_seconds or lower the token budget so the "
                "transcript is decomposed into more requests."
            ) from error
        wall_ms = int((time.monotonic() - started) * 1000)

        if completed.returncode != 0:
            raise BackendResponseError(
                f"backend {self.name!r} exited {completed.returncode}: "
                f"{_tail(completed.stderr)}"
            )
        return self._read_result(completed.stdout, wall_ms)

    def _read_result(self, stdout: str, wall_ms: int) -> ModelResponse:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError as error:
            raise BackendResponseError(
                f"backend {self.name!r} did not return JSON: {error}; "
                f"output began {stdout[:200]!r}"
            ) from error

        if payload.get("is_error"):
            raise BackendResponseError(
                f"backend {self.name!r} reported an error: "
                f"{str(payload.get('result'))[:400]}"
            )
        text = payload.get("result")
        if not isinstance(text, str) or not text.strip():
            raise BackendResponseError(f"backend {self.name!r} returned an empty result")

        usage = payload.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        return ModelResponse(
            text=text,
            usage=TokenUsage(
                input_tokens=self._count(usage, "input_tokens"),
                output_tokens=self._count(usage, "output_tokens"),
                cached_input_tokens=self._count(usage, "cache_read_input_tokens")
                + self._count(usage, "cache_creation_input_tokens"),
            ),
            # The CLI's own timing excludes process startup; the wall clock is what the
            # operator waits, so that is what gets reported.
            wall_ms=wall_ms,
        )


    @staticmethod
    def _count(usage: dict[str, object], key: str) -> int:
        """Read one token count, or say which field was unreadable and why.

        The CLI's usage schema is not this repository's to guarantee. If a field
        arrives as a string, a float, or something else entirely, converting it
        blindly would raise `ValueError` or `TypeError` out of a backend -- past the
        `BackendError` handling in `cli.py` -- and a schema change on the far side
        would surface as a traceback rather than as a backend failure. Cost figures
        are the point of this class, so a bad count is an error rather than a zero.
        """
        value = usage.get(key)
        if value is None:
            return 0
        try:
            return int(value)  # type: ignore[call-overload]
        except (TypeError, ValueError) as error:
            raise BackendResponseError(
                f"backend usage field {key!r} was not a number: {type(value).__name__} "
                f"({str(value)[:80]!r})"
            ) from error


def _tail(stream: str, limit: int = 400) -> str:
    """Last few hundred characters of a stream, for an error message.

    Truncated rather than reproduced in full: the CLI's diagnostics are not expected to
    carry credential material, and a bounded excerpt keeps it that way by construction.
    """
    text = (stream or "").strip()
    return text[-limit:] if text else "(no stderr)"
