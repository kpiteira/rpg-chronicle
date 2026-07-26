"""The one vendor-bound module, tested without reaching the vendor.

Every test here drives `ClaudeCliBackend` through a stubbed subprocess or a canned
stdout payload. Nothing spawns a real CLI, so this suite runs in CI without a
subscription — which is also the reason the measured runs in `docs/ANALYSIS.md` are
documented commands rather than tests.
"""

from __future__ import annotations

import json
import subprocess

import pytest

from rpg_chronicle.analysis.backend import (
    BackendResponseError,
    BackendUnavailableError,
    ModelRequest,
)
from rpg_chronicle.analysis.claude_cli import ClaudeCliBackend

REQUEST = ModelRequest(system="be helpful", user="a transcript")


def _stdout(**overrides) -> str:
    payload = {
        "is_error": False,
        "result": '{"ok": true}',
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "cache_read_input_tokens": 5,
            "cache_creation_input_tokens": 7,
        },
    }
    payload.update(overrides)
    return json.dumps(payload)


def _completed(stdout: str, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=["claude"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_the_invocation_stays_stripped_down():
    """The lean flags are load-bearing, not incidental.

    A default headless session carries roughly 35,000 tokens of system prompt and tool
    definitions before any transcript is added. If these flags are dropped, every cost
    figure this package reports changes by two orders of magnitude at the low end.
    """
    argv = ClaudeCliBackend()._argv(REQUEST)
    assert "--system-prompt" in argv
    assert argv[argv.index("--system-prompt") + 1] == REQUEST.system
    for flag in ("--tools", "--strict-mcp-config", "--setting-sources", "-p"):
        assert flag in argv, flag
    # The prompt goes over stdin, never as an argument: a four-hour transcript would
    # exceed the platform argument limit.
    assert REQUEST.user not in argv


def test_a_missing_executable_is_an_unavailable_backend_not_a_crash(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(BackendUnavailableError, match="on PATH"):
        ClaudeCliBackend().preflight()


def test_usage_counts_are_read_from_the_backend(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(_stdout()))
    response = ClaudeCliBackend().complete(REQUEST)
    assert response.usage.input_tokens == 100
    assert response.usage.output_tokens == 20
    # Cache reads and cache creation are both input the request presented.
    assert response.usage.cached_input_tokens == 12
    assert response.usage.billed_input_tokens == 112


def test_absent_usage_fields_count_as_zero_rather_than_failing(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(_stdout(usage={})))
    assert ClaudeCliBackend().complete(REQUEST).usage.input_tokens == 0


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": "lots"},
        {"input_tokens": {"nested": 1}},
        {"output_tokens": [1, 2]},
    ],
    ids=["string", "object", "list"],
)
def test_an_unreadable_usage_field_becomes_a_backend_error(monkeypatch, usage):
    """A schema change on the far side must not escape as a raw TypeError.

    `cli.py` catches `BackendError`. A bare `ValueError` from an `int()` call would
    travel straight past it and surface as a traceback from inside the transport, and
    a cost figure is exactly the thing that must not be silently wrong.
    """
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(_stdout(usage=usage)))
    with pytest.raises(BackendResponseError, match="was not a number"):
        ClaudeCliBackend().complete(REQUEST)


def test_a_non_object_usage_payload_is_ignored_rather_than_fatal(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: _completed(_stdout(usage="none")))
    assert ClaudeCliBackend().complete(REQUEST).usage.input_tokens == 0


@pytest.mark.parametrize(
    ("stdout", "returncode", "match"),
    [
        ("not json", 0, "did not return JSON"),
        (_stdout(is_error=True, result="model overloaded"), 0, "reported an error"),
        (_stdout(result=""), 0, "empty result"),
        (_stdout(result=None), 0, "empty result"),
        ("", 1, "exited 1"),
    ],
    ids=["not-json", "error-flag", "empty-result", "null-result", "non-zero-exit"],
)
def test_transport_failures_are_backend_errors(monkeypatch, stdout, returncode, match):
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed(stdout, returncode, stderr="boom")
    )
    with pytest.raises(BackendResponseError, match=match):
        ClaudeCliBackend().complete(REQUEST)


def test_a_timeout_says_what_to_do_about_it(monkeypatch):
    def _raise(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=1)

    monkeypatch.setattr(subprocess, "run", _raise)
    with pytest.raises(BackendResponseError, match="lower the token budget"):
        ClaudeCliBackend(timeout_seconds=1).complete(REQUEST)


def test_stderr_in_an_error_message_is_bounded(monkeypatch):
    """Bounded by construction, because this is the one place external output escapes."""
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: _completed("", 1, stderr="x" * 5000)
    )
    with pytest.raises(BackendResponseError) as caught:
        ClaudeCliBackend().complete(REQUEST)
    assert len(str(caught.value)) < 700
