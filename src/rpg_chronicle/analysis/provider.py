"""A model-backed `AnalysisProvider`, assembled from parts that do not know each other.

This is the only module that holds the backend, the prompts, and the decomposition at
once, and even here it holds them by their interfaces. It contains no vendor name, and
a test in `tests/test_vendor_neutrality.py` fails if one appears.

Evidence discipline is enforced here and nowhere else can relax it. Model output is
untrusted: every cited turn id is resolved against the turns the provider was actually
given, through `model.evidence_for`, which raises on an id the session does not
contain. A model that invents a citation aborts the run. That is deliberate. The
alternative -- dropping the offending claim and carrying on -- would convert a loud,
diagnosable hallucination into a quietly shorter summary, which is exactly the failure
mode `docs/PRODUCT.md` calls "unsupported facts without warning".
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from ..model import ReviewQuestion, Scene, TranscriptTurn, evidence_for
from ..providers import AnalysisResult
from .backend import BackendResponseError, ModelBackend, ModelRequest, TokenUsage
from .decompose import TokenBudget, Window, plan_windows
from .prompts import (
    synthesis_system_prompt,
    synthesis_user_prompt,
    window_system_prompt,
    window_user_prompt,
)

DEFAULT_MAX_QUESTIONS = 10
"""The attention budget, expressed as questions rather than as a vague intention.

`docs/PRODUCT.md` puts the north star at around five minutes of review for a four-hour
session. Ten questions at roughly thirty seconds each is that five minutes. The bound
is a constructor argument so it can be tightened, but it exists whether or not anyone
sets it: an analysis pass that emits eighty correct questions has failed.
"""

_CONSEQUENCES = {"low", "medium", "high"}


class AnalysisFormatError(BackendResponseError):
    """The model did not return the JSON object it was asked for."""


@dataclass
class AnalysisCost:
    """What a full analysis pass actually consumed. Measured, never estimated."""

    requests: int = 0
    usage: TokenUsage = field(default_factory=lambda: TokenUsage(0, 0))
    wall_ms: int = 0
    windows: int = 0
    fit_in_one_request: bool = True
    format_retries: int = 0
    """Requests that had to be asked again because the reply was not parseable JSON.

    Reported rather than hidden: a run that needed three retries cost three extra
    requests, and a rising number here is a prompt problem worth knowing about.
    """

    def record(self, *, usage: TokenUsage, wall_ms: int) -> None:
        self.requests += 1
        self.usage = self.usage + usage
        self.wall_ms += wall_ms

    def to_dict(self) -> dict[str, Any]:
        return {
            "requests": self.requests,
            "input_tokens": self.usage.input_tokens,
            "cached_input_tokens": self.usage.cached_input_tokens,
            "billed_input_tokens": self.usage.billed_input_tokens,
            "output_tokens": self.usage.output_tokens,
            "wall_ms": self.wall_ms,
            "windows": self.windows,
            "fit_in_one_request": self.fit_in_one_request,
            "format_retries": self.format_retries,
        }


def _parse_json_object(text: str) -> dict[str, Any]:
    """Recover the JSON object from a response that may be wrapped in chatter.

    Models are told to return bare JSON and usually do. Stripping a code fence or a
    sentence of preamble is tolerance for a formatting habit, not tolerance for wrong
    content: nothing here repairs, invents, or drops a field.
    """
    candidate = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise AnalysisFormatError(
                "the model returned no JSON object; first 200 characters: "
                f"{text.strip()[:200]!r}"
            )
        candidate = candidate[start : end + 1]
    try:
        # strict=False permits literal newlines and tabs inside string values, which
        # models emit when a summary runs to several paragraphs. It changes what
        # counts as well-formed *syntax* and nothing about content: no field is
        # invented, defaulted, or dropped by allowing it.
        parsed = json.loads(candidate, strict=False)
    except json.JSONDecodeError as error:
        raise AnalysisFormatError(f"the model returned malformed JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise AnalysisFormatError(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


def _required_str(payload: dict[str, Any], key: str, *, where: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AnalysisFormatError(f"{where}: missing or empty string field {key!r}")
    return value.strip()


def _turn_ids(payload: dict[str, Any], *, where: str) -> list[str]:
    value = payload.get("turn_ids")
    if not isinstance(value, list) or not value:
        raise AnalysisFormatError(f"{where}: 'turn_ids' must be a non-empty list")
    ids = [item for item in value if isinstance(item, str) and item.strip()]
    if len(ids) != len(value):
        raise AnalysisFormatError(f"{where}: 'turn_ids' contains a non-string entry")
    return ids


def _confidence(payload: dict[str, Any], *, where: str) -> float:
    value = payload.get("confidence")
    if not isinstance(value, int | float) or isinstance(value, bool):
        raise AnalysisFormatError(f"{where}: 'confidence' must be a number")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise AnalysisFormatError(f"{where}: 'confidence' must lie in [0, 1], got {number}")
    return number


def _consequence(payload: dict[str, Any], *, where: str) -> str:
    value = payload.get("consequence")
    if value not in _CONSEQUENCES:
        raise AnalysisFormatError(
            f"{where}: 'consequence' must be one of {sorted(_CONSEQUENCES)}, got {value!r}"
        )
    return str(value)


class TurnIdResolver:
    """Resolves a cited turn id to a real one, or refuses.

    Measured behaviour, not a hypothetical: when a four-hour transcript is decomposed,
    the model cited `turn-740` for a turn the transcript renders as `turn-00740`. It
    named the right turn in the wrong format, the way it sometimes wraps bare JSON in
    a code fence. See `docs/ANALYSIS.md` for the run this came from.

    This is deliberately not a fuzzy match and it does not soften `evidence_for`. The
    only tolerated difference is leading zeros in the numeric part, which is injective
    over a real id set: `turn-00740` and `turn-740` denote the same integer and no two
    distinct real ids can collapse together unless they already differ only in padding
    -- and in that case both are dropped from the fallback index, so the citation
    fails rather than resolving to a coin flip.

    Anything else -- an id for a turn that does not exist, an id from a different
    excerpt, a plausible-looking invention -- still raises. That is the whole point.
    """

    _NUMERIC = re.compile(r"^(.*?)(\d+)$")

    def __init__(self, known_ids: set[str]) -> None:
        self._known = known_ids
        index: dict[str, str | None] = {}
        for turn_id in known_ids:
            key = self._canonical(turn_id)
            if key is None:
                continue
            # A canonical form claimed by two real ids is ambiguous, so it resolves to
            # nothing. Failing closed beats guessing which turn was meant.
            index[key] = None if key in index else turn_id
        self._canonical_index = {key: value for key, value in index.items() if value}

    @classmethod
    def _canonical(cls, turn_id: str) -> str | None:
        match = cls._NUMERIC.match(turn_id.strip())
        if not match:
            return None
        prefix, digits = match.groups()
        return f"{prefix}{int(digits)}"

    def resolve(self, cited: list[str], *, where: str, what: str) -> list[str]:
        resolved: list[str] = []
        unresolved: list[str] = []
        for turn_id in cited:
            if turn_id in self._known:
                resolved.append(turn_id)
                continue
            key = self._canonical(turn_id)
            match = self._canonical_index.get(key) if key else None
            if match:
                resolved.append(match)
            else:
                unresolved.append(turn_id)
        if unresolved:
            raise AnalysisFormatError(
                f"{where}: {what} cites turns absent from its excerpt: {unresolved}"
            )
        return resolved


@dataclass(frozen=True)
class _QuestionDraft:
    issue: str
    recommendation: str | None
    why_it_matters: str
    turn_ids: list[str]
    confidence: float
    consequence: str

    @property
    def priority(self) -> tuple[int, float]:
        """Most consequential first, and among equals the least confident first.

        A high-consequence claim the model is sure about is worth less of a person's
        attention than a high-consequence claim it is guessing at.
        """
        weight = {"high": 3, "medium": 2, "low": 1}[self.consequence]
        return (weight, 1.0 - self.confidence)


def _question_draft(payload: dict[str, Any], *, where: str) -> _QuestionDraft:
    recommendation = payload.get("recommendation")
    if recommendation is not None and not isinstance(recommendation, str):
        raise AnalysisFormatError(f"{where}: 'recommendation' must be a string or null")
    return _QuestionDraft(
        issue=_required_str(payload, "issue", where=where),
        recommendation=recommendation.strip() if isinstance(recommendation, str) else None,
        why_it_matters=_required_str(payload, "why_it_matters", where=where),
        turn_ids=_turn_ids(payload, where=where),
        confidence=_confidence(payload, where=where),
        consequence=_consequence(payload, where=where),
    )


class ModelAnalysisProvider:
    """Generates scenes, a session summary, and review questions with a real model.

    Satisfies the `AnalysisProvider` protocol, so the pipeline treats it exactly as it
    treats the fixture provider and never learns that a model is involved.
    """

    name = "model-analysis"
    is_declared_truth = False

    def __init__(
        self,
        backend: ModelBackend,
        *,
        budget: TokenBudget | None = None,
        max_questions: int = DEFAULT_MAX_QUESTIONS,
        format_retries: int = 1,
    ) -> None:
        if max_questions < 1:
            raise ValueError("max_questions must be at least 1")
        if format_retries < 0:
            raise ValueError("format_retries cannot be negative")
        self._backend = backend
        self._budget = budget or TokenBudget()
        self._max_questions = max_questions
        self._format_retries = format_retries
        self.cost = AnalysisCost()

    @property
    def backend_name(self) -> str:
        return self._backend.name

    @property
    def model(self) -> str:
        return self._backend.model

    def preflight(self) -> None:
        """Check the backend before anything is written anywhere.

        `analyze` calls this too, but a caller that runs it first turns a missing
        credential into an error before the pipeline has created a session directory,
        which is the difference between a clean failure and a half-written session.
        """
        self._backend.preflight()

    def _ask(self, system: str, user: str) -> dict[str, Any]:
        """One exchange, retried only when the reply was not parseable JSON.

        The distinction matters. A reply that is not JSON is a formatting failure and
        asking again is reasonable -- a four-hour pass that has already spent eight
        minutes should not be discarded because the last window arrived with a stray
        newline in a string. A reply that cites a turn which does not exist is not a
        formatting failure, and it is never retried: it aborts, loudly, every time.
        Retrying that would be a slow way of sampling until the model stops getting
        caught, which is precisely the softening this provider must not do.

        Retries are counted in the cost report like any other request, because they
        were paid for.
        """
        attempts = self._format_retries + 1
        last_error: AnalysisFormatError | None = None
        for attempt in range(attempts):
            message = user
            if attempt:
                message = (
                    f"{user}\n\nYour previous reply could not be parsed: "
                    f"{last_error}. Reply again with a single well-formed JSON object "
                    "and nothing else."
                )
            started = time.monotonic()
            response = self._backend.complete(ModelRequest(system=system, user=message))
            elapsed = response.wall_ms or int((time.monotonic() - started) * 1000)
            self.cost.record(usage=response.usage, wall_ms=elapsed)
            try:
                return _parse_json_object(response.text)
            except AnalysisFormatError as error:
                last_error = error
                if attempt + 1 < attempts:
                    self.cost.format_retries += 1
        raise last_error if last_error else AnalysisFormatError("no reply was parsed")

    def _analyze_window(self, window: Window, total: int) -> dict[str, Any]:
        payload = self._ask(
            window_system_prompt(max_questions=self._max_questions),
            window_user_prompt(window.turns, index=window.index, total=total),
        )
        where = f"window {window.index + 1}"
        scenes = payload.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise AnalysisFormatError(f"{where}: 'scenes' must be a non-empty list")

        # Cited ids are checked against the excerpt the model was shown, not the whole
        # session. A window that cites a turn from a different window has not made a
        # supported claim; it has guessed at material it never saw. This is stricter
        # than `evidence_for`, which can only see whether an id exists somewhere in
        # the session, and it is applied to everything that becomes a product claim:
        # scenes and questions. Resolution rewrites the citation to the real id, so
        # everything downstream works in the session's own vocabulary.
        resolver = TurnIdResolver(window.turn_ids)
        for scene in scenes:
            if not isinstance(scene, dict):
                raise AnalysisFormatError(f"{where}: a scene entry is not an object")
            scene["turn_ids"] = resolver.resolve(
                _turn_ids(scene, where=where), where=where, what="a scene"
            )
        for question in payload.get("questions") or []:
            if isinstance(question, dict):
                question["turn_ids"] = resolver.resolve(
                    _turn_ids(question, where=where), where=where, what="a question"
                )
        return {
            "window_summary": _required_str(payload, "window_summary", where=where),
            "scenes": scenes,
            "entities": payload.get("entities") or [],
            "threads": payload.get("threads") or [],
            "questions": payload.get("questions") or [],
        }

    def _synthesize(
        self,
        window_payloads: list[dict[str, Any]],
        candidates: list[_QuestionDraft],
        resolver: TurnIdResolver,
    ) -> tuple[str, list[_QuestionDraft]]:
        payload = self._ask(
            synthesis_system_prompt(max_questions=self._max_questions),
            synthesis_user_prompt(window_payloads),
        )
        summary = _required_str(payload, "summary", where="synthesis")
        raw = payload.get("questions")
        if not isinstance(raw, list):
            raise AnalysisFormatError("synthesis: 'questions' must be a list")
        # Synthesis sees the whole session's findings, so it may cite any real turn --
        # but only a real one. It was never shown the transcript and has no business
        # inventing an id it did not receive.
        for item in raw:
            if isinstance(item, dict):
                item["turn_ids"] = resolver.resolve(
                    _turn_ids(item, where="synthesis"),
                    where="synthesis",
                    what="a question",
                )
        questions = [
            _question_draft(item, where="synthesis")
            for item in raw
            if isinstance(item, dict)
        ]
        # If synthesis returns nothing usable, the per-excerpt candidates are the
        # honest fallback: they were supported by turns the model actually read.
        return summary, questions or candidates

    def analyze(self, turns: list[TranscriptTurn]) -> AnalysisResult:
        if not turns:
            raise ValueError("analysis requires at least one transcript turn")

        self._backend.preflight()
        self.cost = AnalysisCost()

        windows = plan_windows(turns, self._budget)
        self.cost.windows = len(windows)
        self.cost.fit_in_one_request = len(windows) == 1

        window_payloads = [self._analyze_window(window, len(windows)) for window in windows]

        candidates: list[_QuestionDraft] = []
        for index, payload in enumerate(window_payloads):
            for item in payload["questions"]:
                if isinstance(item, dict):
                    candidates.append(_question_draft(item, where=f"window {index + 1}"))

        turns_by_id = {turn.id: turn for turn in turns}

        if len(windows) == 1:
            summary = window_payloads[0]["window_summary"]
            drafts = candidates
        else:
            summary, drafts = self._synthesize(
                window_payloads, candidates, TurnIdResolver(set(turns_by_id))
            )

        scenes: list[Scene] = []
        seen_spans: set[tuple[str, ...]] = set()
        for payload in window_payloads:
            for entry in payload["scenes"]:
                ids = tuple(_turn_ids(entry, where="scene"))
                # Windows overlap, so a scene on a boundary is reported twice. The
                # cited span is the identity: the same turns are the same scene.
                if ids in seen_spans:
                    continue
                seen_spans.add(ids)
                scenes.append(
                    Scene(
                        id=f"scene-{len(scenes) + 1:03d}",
                        title=_required_str(entry, "title", where="scene"),
                        summary=_required_str(entry, "summary", where="scene"),
                        evidence=evidence_for(turns_by_id, list(ids)),
                    )
                )

        questions = self._bounded_questions(drafts, turns_by_id)

        native = {
            "provider": self.name,
            "backend": self._backend.name,
            "model": self._backend.model,
            "is_declared_truth": False,
            "cost": self.cost.to_dict(),
            "budget": {
                "max_input_tokens": self._budget.max_input_tokens,
                "overlap_turns": self._budget.overlap_turns,
            },
            "max_questions": self._max_questions,
            "questions_before_bound": len(drafts),
            "windows": window_payloads,
        }
        return AnalysisResult(
            summary=summary,
            scenes=scenes,
            review_questions=questions,
            native_artifact=native,
        )

    def _bounded_questions(
        self,
        drafts: list[_QuestionDraft],
        turns_by_id: dict[str, TranscriptTurn],
    ) -> list[ReviewQuestion]:
        """Deduplicate, prioritise, and cap the queue.

        The cap is applied here rather than trusted to the prompt. A model asked for
        at most ten questions usually returns at most ten; "usually" is not a bound.
        """
        unique: list[_QuestionDraft] = []
        seen: set[str] = set()
        for draft in drafts:
            key = draft.issue.strip().casefold()
            if key in seen:
                continue
            seen.add(key)
            unique.append(draft)

        ranked = sorted(unique, key=lambda draft: draft.priority, reverse=True)
        return [
            ReviewQuestion(
                id=f"question-{index + 1:03d}",
                issue=draft.issue,
                recommendation=draft.recommendation,
                why_it_matters=draft.why_it_matters,
                evidence=evidence_for(turns_by_id, draft.turn_ids),
                confidence=draft.confidence,
                consequence=draft.consequence,
            )
            for index, draft in enumerate(ranked[: self._max_questions])
        ]
