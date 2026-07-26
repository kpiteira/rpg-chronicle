"""Command line entry point.

Provider selection lives here and only here. `pipeline.py` receives constructed
providers and never learns which kind it was handed, so pointing the slice at a real
model is a wiring change in this file, exactly as `docs/DECISIONS.md` D-008 promised.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from .analysis.backend import BackendError, BackendUnavailableError
from .analysis.claude_cli import DEFAULT_MODEL, ClaudeCliBackend
from .analysis.decompose import TokenBudget
from .analysis.provider import DEFAULT_MAX_QUESTIONS, ModelAnalysisProvider
from .pipeline import run_pipeline
from .providers import FixtureAnalysisProvider, FixtureTranscriptProvider
from .transcription.engine import EngineError, EngineUnavailableError
from .transcription.provider import SpeechTranscriptProvider
from .transcription.sherpa_diarization import (
    DEFAULT_CLUSTER_THRESHOLD,
    SherpaDiarizationEngine,
)
from .transcription.whisper_cpp import DEFAULT_MODEL_FILENAME, WhisperCppEngine

DEFAULT_MODEL_DIR = Path.home() / ".cache/rpg-chronicle/models"
"""Where the speech models live by default.

Outside the repository on purpose: they are large binaries and `.gitignore` excludes
`models/` for the same reason it excludes audio. `research/probes/README.md` documents
the downloads.
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rpg-chronicle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_fixture = subparsers.add_parser("run-fixture", help="run the synthetic vertical slice")
    run_fixture.add_argument("fixture", type=Path)
    run_fixture.add_argument("--output", type=Path, required=True)
    run_fixture.add_argument(
        "--analysis",
        choices=["fixture", "model"],
        default="fixture",
        help=(
            "fixture: replay declared analysis truth, which proves nothing about "
            "analysis quality. model: generate analysis with a real model."
        ),
    )
    run_fixture.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="which model to ask, when --analysis model is selected",
    )
    run_fixture.add_argument(
        "--max-input-tokens",
        type=int,
        default=TokenBudget().max_input_tokens,
        help=(
            "the per-request budget that decides whether the transcript is decomposed. "
            "Lower it to force decomposition on a transcript that would otherwise fit."
        ),
    )
    run_fixture.add_argument(
        "--overlap-turns",
        type=int,
        default=TokenBudget().overlap_turns,
        help="turns repeated across a window boundary so a straddling scene is seen whole",
    )
    run_fixture.add_argument(
        "--max-questions",
        type=int,
        default=DEFAULT_MAX_QUESTIONS,
        help="hard cap on the review queue; the attention budget, not a suggestion",
    )
    run_fixture.add_argument(
        "--cost-report",
        type=Path,
        help="write measured tokens, wall time, and request count to this path",
    )

    run_audio = subparsers.add_parser(
        "run-audio",
        help="carry a real recording from audio to a review package",
        description=(
            "Recognition with whisper.cpp, speaker labels from sherpa-onnx, then the "
            "same canonical path the synthetic slice uses. Requires 16 kHz mono audio: "
            "the probe measured conversion cost separately and this command will not "
            "silently resample. Nothing it writes belongs in the repository."
        ),
    )
    run_audio.add_argument("audio", type=Path)
    run_audio.add_argument("--output", type=Path, required=True)
    run_audio.add_argument(
        "--session-id",
        help="names the session directory; defaults to the audio file stem",
    )
    run_audio.add_argument(
        "--analysis",
        choices=["fixture", "model"],
        default="model",
        help=(
            "model (default here): generate analysis with a real model. Unlike "
            "run-fixture, freshly recognized audio carries no declared truth to replay, "
            "so there is nothing for a fixture provider to read; selecting fixture "
            "requires --analysis-fixture. run-fixture keeps its own fixture default for "
            "the CI reason in docs/ANALYSIS.md, which does not apply here because CI "
            "cannot run this command at all -- the audio is not in the repository."
        ),
    )
    run_audio.add_argument(
        "--analysis-fixture",
        type=Path,
        help="a fixture carrying declared analysis truth, when --analysis fixture is used",
    )
    run_audio.add_argument("--model", default=DEFAULT_MODEL, help="which model to ask")
    run_audio.add_argument(
        "--max-input-tokens", type=int, default=TokenBudget().max_input_tokens
    )
    run_audio.add_argument("--overlap-turns", type=int, default=TokenBudget().overlap_turns)
    run_audio.add_argument("--max-questions", type=int, default=DEFAULT_MAX_QUESTIONS)
    run_audio.add_argument(
        "--model-dir",
        type=Path,
        default=DEFAULT_MODEL_DIR,
        help=f"directory holding the speech models (default: {DEFAULT_MODEL_DIR})",
    )
    run_audio.add_argument(
        "--whisper-model",
        type=Path,
        help=f"ggml model file; defaults to <model-dir>/{DEFAULT_MODEL_FILENAME}",
    )
    run_audio.add_argument(
        "--no-diarize",
        action="store_true",
        help=(
            "skip speaker labelling. The labels are marked unreliable either way; this "
            "drops them entirely rather than carrying ones you do not want."
        ),
    )
    run_audio.add_argument(
        "--cluster-threshold",
        type=float,
        default=DEFAULT_CLUSTER_THRESHOLD,
        help=(
            "diarization clustering threshold. Raising it merges distinct speakers, "
            "which fabricates attribution; the default is low deliberately."
        ),
    )
    run_audio.add_argument(
        "--run-report",
        type=Path,
        help=(
            "write shape, counts and timing to this path. Carries no recognized text, "
            "so it is safe to commit as evidence for a restricted recording."
        ),
    )
    return parser


def _model_provider(args: argparse.Namespace) -> ModelAnalysisProvider:
    """Construct the model-backed provider from the parsed flags.

    Overridden in tests to inject a backend that does not reach a vendor.
    """
    return ModelAnalysisProvider(
        ClaudeCliBackend(model=args.model),
        budget=TokenBudget(
            max_input_tokens=args.max_input_tokens,
            overlap_turns=args.overlap_turns,
        ),
        max_questions=args.max_questions,
    )


def _fixture_provider(fixture: Path) -> FixtureAnalysisProvider:
    payload = json.loads(fixture.read_text())
    if "expected_analysis" not in payload:
        raise SystemExit(
            f"{fixture} carries no 'expected_analysis' block, so there is no declared "
            "truth to replay. Long-form fixtures are deliberately shipped without one: "
            "run them with --analysis model."
        )
    return FixtureAnalysisProvider(fixture)


def _run_fixture(args: argparse.Namespace) -> None:
    session_id = json.loads(args.fixture.read_text())["session"]["id"]

    if args.analysis == "model":
        try:
            provider: FixtureAnalysisProvider | ModelAnalysisProvider = _model_provider(args)
        except ValueError as error:
            # A budget with no room for the prompt, a negative overlap, a question cap
            # of zero. These are usage errors and deserve a usage error's message
            # rather than a traceback from three modules down.
            raise SystemExit(f"invalid analysis options: {error}") from error
        # Fail before the pipeline creates a session directory. `run_pipeline` writes
        # the canonical session the moment it is called, so this ordering is the only
        # thing standing between an unusable backend and a half-written session.
        provider.preflight()
    else:
        provider = _fixture_provider(args.fixture)

    session = run_pipeline(
        source=args.fixture,
        output_dir=args.output,
        transcript_provider=FixtureTranscriptProvider(),
        analysis_provider=provider,
        session_id=session_id,
    )

    print(f"{session.session_id}: {session.status}")
    if isinstance(provider, ModelAnalysisProvider):
        cost = provider.cost
        print(
            f"analysis provider: model output via {provider.backend_name} "
            f"({provider.model}) — not declared truth"
        )
        print(
            f"cost: {cost.requests} requests, "
            f"{cost.usage.billed_input_tokens} input tokens, "
            f"{cost.usage.output_tokens} output tokens, "
            f"{cost.wall_ms / 1000:.1f}s wall"
        )
        print(
            f"decomposition: {cost.windows} window(s); "
            f"fit in one request: {cost.fit_in_one_request}"
        )
        print(f"review questions: {len(session.review_questions)} (cap {args.max_questions})")
        if args.cost_report:
            report = {
                "session_id": session.session_id,
                "fixture": str(args.fixture),
                "backend": provider.backend_name,
                "model": provider.model,
                "is_declared_truth": False,
                "max_input_tokens": args.max_input_tokens,
                "max_questions": args.max_questions,
                "transcript_turns": len(session.turns),
                "scenes": len(session.scenes),
                "review_questions": len(session.review_questions),
                **cost.to_dict(),
            }
            args.cost_report.parent.mkdir(parents=True, exist_ok=True)
            args.cost_report.write_text(json.dumps(report, indent=2) + "\n")
            print(f"cost report: {args.cost_report}")
    else:
        print("analysis provider: fixture (declared truth, not model output)")


def _transcript_provider(args: argparse.Namespace) -> SpeechTranscriptProvider:
    """Construct the speech provider from the parsed flags.

    Overridden in tests to inject engines that do not need a model file or audio.
    """
    whisper_model = args.whisper_model or (args.model_dir / DEFAULT_MODEL_FILENAME)
    recognizer = WhisperCppEngine(model=whisper_model)
    diarizer = (
        None
        if args.no_diarize
        else SherpaDiarizationEngine(
            model_dir=args.model_dir, cluster_threshold=args.cluster_threshold
        )
    )
    return SpeechTranscriptProvider(recognizer, diarizer)


def _run_report(args: argparse.Namespace, session: Any, provider: Any, wall_s: float) -> dict:
    """Shape, counts and timing -- and deliberately not one word of what was said.

    This is the committable evidence for a run over restricted audio. Every field is a
    count, a duration, or a label the engines invented; none is derived from the
    recording in a way that reproduces it.
    """
    native = session.processor_artifacts
    turns = session.turns
    cited: set[str] = set()
    for claim in list(session.scenes) + list(session.review_questions):
        cited |= set(claim.evidence.turn_ids)
    spans = [turn.end_ms - turn.start_ms for turn in turns]
    scored = [turn.confidence for turn in turns if turn.confidence is not None]
    labelled = [turn.physical_speaker for turn in turns if turn.physical_speaker]
    return {
        "session_id": session.session_id,
        "audio": args.audio.name,
        "status": session.status,
        # Follows the provider actually used. Hardcoding "model output" would have
        # labelled a fixture-backed run's declared truth as something a model produced,
        # which is the exact confusion shared rule 9 exists to prevent.
        "output_kind": (
            "declared truth"
            if session.provenance.get("analysis_is_declared_truth")
            else "model output"
        ),
        "transcript_provider": session.provenance.get("transcript_provider"),
        "analysis_provider": session.provenance.get("analysis_provider"),
        "analysis_is_declared_truth": session.provenance.get("analysis_is_declared_truth"),
        "wall_clock_s": round(wall_s, 1),
        "turns": len(turns),
        "total_turn_span_ms": sum(spans),
        "turns_with_confidence": len(scored),
        "turns_with_speaker": len(labelled),
        "distinct_speaker_labels": len(set(labelled)),
        "speaker_labels_are": "cluster identifiers, not people; marked unreliable",
        "confidence_mean": round(sum(scored) / len(scored), 4) if scored else None,
        "confidence_min": round(min(scored), 4) if scored else None,
        "scenes": len(session.scenes),
        "review_questions": len(session.review_questions),
        # Evidence integrity as counts. `model.evidence_for` already refuses a claim
        # citing a turn the session lacks, so `claims_citing_missing_turns` is 0 or the
        # run did not finish -- but recording it means the report carries the check
        # rather than a document asserting somebody performed it.
        "claims": len(session.scenes) + len(session.review_questions),
        "distinct_cited_turn_ids": len(cited),
        "claims_citing_missing_turns": len(cited - {turn.id for turn in turns}),
        "turns_with_timestamps": sum(
            1 for turn in turns if turn.end_ms > turn.start_ms >= 0
        ),
        "processor_artifacts": dict(native),
        "contains_recognized_text": False,
    }


def _run_audio(args: argparse.Namespace) -> None:
    if args.analysis == "model":
        try:
            analysis: FixtureAnalysisProvider | ModelAnalysisProvider = _model_provider(args)
        except ValueError as error:
            raise SystemExit(f"invalid analysis options: {error}") from error
    else:
        if args.analysis_fixture is None:
            raise SystemExit(
                "--analysis fixture needs --analysis-fixture pointing at a file with an "
                "'expected_analysis' block. Recognized audio carries no declared truth "
                "of its own, so there is nothing to replay without one."
            )
        analysis = _fixture_provider(args.analysis_fixture)

    transcript = _transcript_provider(args)
    # Both preflights before the pipeline writes anything. A missing model file or an
    # unauthenticated backend should cost a second, not twenty minutes of recognition
    # followed by a failure and a half-written session.
    transcript.preflight()
    if isinstance(analysis, ModelAnalysisProvider):
        analysis.preflight()

    started = time.monotonic()
    session = run_pipeline(
        source=args.audio,
        output_dir=args.output,
        transcript_provider=transcript,
        analysis_provider=analysis,
        session_id=args.session_id or args.audio.stem,
    )
    wall_s = time.monotonic() - started

    print(f"{session.session_id}: {session.status}")
    print(f"transcript provider: {session.provenance.get('transcript_provider')}")
    print(
        f"turns: {len(session.turns)}, "
        f"speaker-labelled: {sum(1 for t in session.turns if t.physical_speaker)} "
        "(labels are cluster ids, marked unreliable)"
    )
    print(f"scenes: {len(session.scenes)}, review questions: {len(session.review_questions)}")
    if isinstance(analysis, ModelAnalysisProvider):
        print(
            f"analysis provider: model output via {analysis.backend_name} "
            f"({analysis.model}) — not declared truth"
        )
    if args.run_report:
        report = _run_report(args, session, transcript, wall_s)
        args.run_report.parent.mkdir(parents=True, exist_ok=True)
        args.run_report.write_text(json.dumps(report, indent=2) + "\n")
        print(f"run report: {args.run_report}")


def main() -> None:
    args = _parser().parse_args()
    handlers = {"run-fixture": _run_fixture, "run-audio": _run_audio}
    try:
        handlers[args.command](args)
    except BackendUnavailableError as error:
        # A configuration failure, not a crash. The message names what is missing
        # and never the value of anything.
        raise SystemExit(f"analysis backend unavailable: {error}") from error
    except BackendError as error:
        raise SystemExit(f"analysis backend failed: {error}") from error
    except EngineUnavailableError as error:
        raise SystemExit(f"speech engine unavailable: {error}") from error
    except EngineError as error:
        raise SystemExit(f"speech engine failed: {error}") from error


if __name__ == "__main__":
    main()
