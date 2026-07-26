"""A backend that answers without a vendor, so the seam can be tested without one.

This is the conformance harness the goal asks for: it proves the abstraction holds by
driving it with something that is emphatically not Claude. If `ModelAnalysisProvider`
or the pipeline ever needed a real vendor to work, none of the tests using this file
would run.

It is a test double, not a second working backend. It does not reach a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from rpg_chronicle.analysis.backend import (
    BackendUnavailableError,
    ModelRequest,
    ModelResponse,
    TokenUsage,
    require_env_credential,
)
from rpg_chronicle.analysis.decompose import render_turn


def _turn_ids_in(prompt: str) -> list[str]:
    """Recover the turn ids the prompt showed us, so replies cite only real turns.

    The rendering is `[turn-00001] (speaker-1) text`, so the ids are the bracketed
    tokens at the start of each line. A fake that invented ids would exercise the
    hallucination path on every test rather than the happy path.
    """
    ids: list[str] = []
    for line in prompt.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            ids.append(stripped[1 : stripped.index("]")])
    return ids


@dataclass
class FakeBackend:
    """Replies with well-formed analysis JSON derived from whatever it was shown."""

    name: str = "fake-backend"
    model: str = "fake-model-1"
    questions_per_window: int = 2
    required_env_var: str | None = None
    available: bool = True
    requests: list[ModelRequest] = field(default_factory=list)
    input_tokens_per_request: int = 1000
    output_tokens_per_request: int = 100

    def preflight(self) -> None:
        if not self.available:
            raise BackendUnavailableError(
                f"backend {self.name!r} is configured as unavailable for this test"
            )
        if self.required_env_var:
            require_env_credential(self.required_env_var, backend_name=self.name)

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        ids = _turn_ids_in(request.user)
        payload = self._synthesis(request) if not ids else self._window(ids)
        return ModelResponse(
            text=json.dumps(payload),
            usage=TokenUsage(
                input_tokens=self.input_tokens_per_request,
                output_tokens=self.output_tokens_per_request,
            ),
            wall_ms=7,
        )

    def _window(self, ids: list[str]) -> dict[str, Any]:
        half = max(1, len(ids) // 2)
        return {
            "window_summary": f"A stretch of play covering {len(ids)} turns.",
            "scenes": [
                {
                    "title": "Opening stretch",
                    "summary": "Something happened and it mattered.",
                    "turn_ids": ids[:half],
                },
                {
                    "title": "Closing stretch",
                    "summary": "Something else happened and it also mattered.",
                    "turn_ids": ids[half:] or ids[:half],
                },
            ],
            "entities": [
                {
                    "name": "A Name",
                    "kind": "character",
                    "aliases": ["Another Name"],
                    "turn_ids": ids[:1],
                }
            ],
            "threads": [{"description": "Something is unresolved.", "turn_ids": ids[:1]}],
            "questions": [
                {
                    "issue": f"Uncertain detail {index} around {ids[index % len(ids)]}.",
                    "recommendation": None if index % 2 else "A recommended answer",
                    "why_it_matters": "It would end up in the campaign record.",
                    "turn_ids": [ids[index % len(ids)]],
                    "confidence": 0.5,
                    "consequence": ["low", "medium", "high"][index % 3],
                }
                for index in range(self.questions_per_window)
            ],
        }

    def _synthesis(self, request: ModelRequest) -> dict[str, Any]:
        """Assemble from the window payloads the provider handed back to us."""
        ids: list[str] = []
        try:
            findings = json.loads(request.user[request.user.index("[") :])
        except (ValueError, json.JSONDecodeError):
            findings = []
        for window in findings if isinstance(findings, list) else []:
            for question in window.get("questions", []):
                ids.extend(question.get("turn_ids", []))
        ids = ids or ["turn-00001"]
        return {
            "summary": "One session, assembled from every excerpt of it.",
            "questions": [
                {
                    "issue": f"Assembled question {index}.",
                    "recommendation": "An answer",
                    "why_it_matters": "It spans more than one excerpt.",
                    "turn_ids": [ids[index % len(ids)]],
                    "confidence": 0.4,
                    "consequence": "high",
                }
                for index in range(self.questions_per_window)
            ],
        }


@dataclass
class ScriptedBackend:
    """Returns exactly the texts it was given, in order. For malformed-output tests."""

    replies: list[str]
    name: str = "scripted-backend"
    model: str = "scripted-model"
    calls: int = 0

    def preflight(self) -> None:
        return None

    def complete(self, request: ModelRequest) -> ModelResponse:
        text = self.replies[min(self.calls, len(self.replies) - 1)]
        self.calls += 1
        return ModelResponse(
            text=text,
            usage=TokenUsage(input_tokens=10, output_tokens=10),
            wall_ms=1,
        )


def rendered_prompt_for(turns: list) -> str:
    """The rendering a backend would see, for tests that assert on prompt content."""
    return "\n".join(render_turn(turn) for turn in turns)
