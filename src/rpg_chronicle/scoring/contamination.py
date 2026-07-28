"""Refusing to score an engine against truth that engine helped write.

`docs/EVALUATION.md` states the rule in prose: an engine that helped build the truth
cannot be scored against it without declaring the dependency, because it is being marked
against its own output. Prose is not enforcement, so the rule lives here as behaviour --
the harness marks every affected dimension and withholds the headline verdict rather than
averaging a contaminated number in with clean ones.

The check fails closed. A manifest that names contaminating providers, run against a
session whose engines cannot be identified, is *undetermined* and is refused. The
alternative -- treating "I could not tell" as "not contaminated" -- would produce exactly
the clean-looking score this module exists to prevent.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Tokens that identify no engine and would match anything. `ggml` is whisper.cpp's file
#: format, `bin` and `en` are a suffix and a language; leaving them in would let a
#: manifest entry of "ggml" declare every whisper.cpp run contaminated.
NOISE_TOKENS = frozenset({"ggml", "bin", "model", "models", "v", "and", "the", "no", "with"})


def tokens(text: str) -> set[str]:
    """Reduce an engine name to comparable tokens.

    A manifest writes ``whisper.cpp large-v3-turbo``; a session records the engine name
    ``whisper.cpp`` and the model file ``ggml-large-v3-turbo.bin`` in two different
    fields. Neither string ever equals the other, so the comparison has to be on tokens
    or it never fires at all -- and a contamination check that never fires is worse than
    none, because it looks like one.
    """
    return {
        token
        for token in re.split(r"[^a-z0-9]+", text.lower())
        if token and token not in NOISE_TOKENS
    }


@dataclass(frozen=True)
class EngineIdentity:
    """Everything the session records about what produced it.

    `sources` names where each string came from, so a reader can tell an engine the
    session declared from one inferred out of an artifact filename.
    """

    strings: list[str] = field(default_factory=list)
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def tokens(self) -> set[str]:
        collected: set[str] = set()
        for value in self.strings:
            collected |= tokens(value)
        return collected

    @property
    def is_known(self) -> bool:
        return bool(self.tokens)


def engine_identity(session: dict[str, Any], session_dir: Path) -> EngineIdentity:
    """Collect engine identity from the session and its native artifacts.

    Canonical provenance records ``whisper.cpp+sherpa-onnx`` -- the engine names but not
    the model. Which whisper model ran is in the engine-native artifact the pipeline
    preserved, and the manifest's contaminating providers are named to model precision
    (``whisper.cpp large-v3-turbo``), so reading only provenance would miss every real
    contamination this corpus can express.
    """
    strings: list[str] = []
    sources: dict[str, str] = {}

    def record(value: Any, where: str) -> None:
        # Keyed by the string, so a name recorded in both provenance and the native
        # artifact -- the ordinary case, since the pipeline copies the engine name into
        # provenance -- is listed once, under the first place it was found.
        if isinstance(value, str) and value.strip() and value not in sources:
            strings.append(value)
            sources[value] = where

    provenance = session.get("provenance") or {}
    for key in ("transcript_provider", "analysis_provider"):
        record(provenance.get(key), f"provenance.{key}")

    for artifact_key, relative in (session.get("processor_artifacts") or {}).items():
        artifact = session_dir / str(relative)
        if not artifact.is_file():
            continue
        try:
            payload = json.loads(artifact.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        _walk(payload, f"processor-native/{artifact_key}", record)

    return EngineIdentity(strings=strings, sources=sources)


#: Field names that carry an engine or a model. Searched at any depth, because a provider
#: that composes engines nests each engine's own artifact under its own key: the real
#: whisper.cpp run records `recognition.model_file`, two levels down, and a top-level-only
#: read of that artifact finds the provider name and never the model. That is not a
#: hypothetical -- it is how the first real run against this harness reported clean.
IDENTITY_FIELDS = ("engine", "model", "model_file", "model_name", "provider", "backend")

#: How deep to look. A native artifact is engine output and therefore untrusted input; a
#: bound keeps a pathological or cyclic-looking document from walking forever.
MAX_ARTIFACT_DEPTH = 6


def _walk(payload: Any, where: str, record: Any, depth: int = 0) -> None:
    if depth > MAX_ARTIFACT_DEPTH:
        return
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key in IDENTITY_FIELDS:
                record(value, f"{where}.{key}")
            if isinstance(value, dict | list):
                _walk(value, f"{where}.{key}", record, depth + 1)
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict | list):
                _walk(item, where, record, depth + 1)


@dataclass(frozen=True)
class ContaminationVerdict:
    """Whether this session may be scored against this manifest's truth, and why.

    `state` is one of ``clean``, ``contaminated``, ``undetermined`` or ``declared_truth``.
    The last is not contamination in the annotation sense and is refused for a different
    reason: a fixture provider replays an answer somebody wrote into the fixture, so
    scoring it measures the fixture author rather than the system.
    """

    state: str
    matched: list[str]
    declared: list[str]
    identity: EngineIdentity
    explanation: str

    @property
    def scoreable(self) -> bool:
        return self.state == "clean"


def assess(
    session: dict[str, Any],
    session_dir: Path,
    contaminating_providers: list[str],
) -> ContaminationVerdict:
    identity = engine_identity(session, session_dir)
    provenance = session.get("provenance") or {}

    if provenance.get("analysis_is_declared_truth"):
        return ContaminationVerdict(
            state="declared_truth",
            matched=[],
            declared=list(contaminating_providers),
            identity=identity,
            explanation=(
                "the session's analysis is declared truth replayed from a fixture "
                f"({provenance.get('analysis_provider')}), not model output. Scoring it "
                "measures whoever wrote the fixture. `docs/EVALUATION.md` and "
                "`providers.FixtureAnalysisProvider` both say this output is never "
                "reported as a result, so the harness declines rather than printing "
                "numbers somebody will quote."
            ),
        )

    if not contaminating_providers:
        return ContaminationVerdict(
            state="clean",
            matched=[],
            declared=[],
            identity=identity,
            explanation=(
                "the manifest declares no contaminating providers, so no engine here is "
                "being marked against its own output"
            ),
        )

    if not identity.is_known:
        return ContaminationVerdict(
            state="undetermined",
            matched=[],
            declared=list(contaminating_providers),
            identity=identity,
            explanation=(
                f"the manifest names {len(contaminating_providers)} contaminating "
                "provider(s) and the session records nothing that identifies the engines "
                "that produced it, so whether this run is being scored against its own "
                "output cannot be decided. That is refused rather than assumed clean: an "
                "unidentifiable engine is the case where a contaminated score would look "
                "exactly like a clean one"
            ),
        )

    session_tokens = identity.tokens
    matched = [
        provider
        for provider in contaminating_providers
        if tokens(provider) and tokens(provider) <= session_tokens
    ]
    if matched:
        return ContaminationVerdict(
            state="contaminated",
            matched=matched,
            declared=list(contaminating_providers),
            identity=identity,
            explanation=(
                f"the truth in this manifest was built with {', '.join(matched)}, which "
                "also produced this session. The run holds an undeclared advantage over "
                "any run that did not write the answer key, so every dimension that "
                "reads the answer key is withheld rather than printed with a warning "
                "beside it"
            ),
        )
    underspecified = _underspecified(identity, contaminating_providers)
    if underspecified:
        return ContaminationVerdict(
            state="undetermined",
            matched=[],
            declared=list(contaminating_providers),
            identity=identity,
            explanation=(
                "the session names an engine that is consistent with "
                f"{', '.join(underspecified)} but records nothing that would settle which "
                "model ran, and the manifest declares contaminating providers to model "
                "precision. Everything the session does say agrees with the declaration; "
                "what is missing is the part that would rule it out. That is refused "
                "rather than reported clean, because an engine identified to family and "
                "not to model is exactly the case where a contaminated score is "
                "indistinguishable from a clean one"
            ),
        )

    return ContaminationVerdict(
        state="clean",
        matched=[],
        declared=list(contaminating_providers),
        identity=identity,
        explanation=(
            f"none of the {len(contaminating_providers)} declared contaminating "
            f"provider(s) matches the engines this session records "
            f"({', '.join(identity.strings)})"
        ),
    )


def _underspecified(identity: EngineIdentity, contaminating_providers: list[str]) -> list[str]:
    """Declared providers the session cannot be cleared of, because it knows too little.

    The test is per recorded string rather than over the union: a session records
    `whisper.cpp` in one field and, when all is well, `ggml-large-v3-turbo.bin` in
    another. If some recorded string's tokens are a *subset* of a declared provider's,
    then everything the session says about that engine agrees with the declaration and the
    only thing separating them is detail the session did not record. The union would hide
    this, because unrelated tokens from the analysis backend would break the subset.

    A genuinely different engine fails the test and stays clean: `whisper.cpp` is not a
    subset of `openai-whisper medium.en`, because `cpp` is not in it.
    """
    matches: list[str] = []
    for provider in contaminating_providers:
        declared = tokens(provider)
        if not declared:
            continue
        for value in identity.strings:
            recorded = tokens(value)
            if recorded and recorded < declared:
                matches.append(provider)
                break
    return matches
