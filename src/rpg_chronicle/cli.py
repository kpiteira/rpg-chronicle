"""Command line entry point.

Provider selection lives here and only here. `pipeline.py` receives constructed
providers and never learns which kind it was handed, so pointing the slice at a real
model is a wiring change in this file, exactly as `docs/DECISIONS.md` D-008 promised.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analysis.backend import BackendError, BackendUnavailableError
from .analysis.claude_cli import DEFAULT_MODEL, ClaudeCliBackend
from .analysis.decompose import TokenBudget
from .analysis.provider import DEFAULT_MAX_QUESTIONS, ModelAnalysisProvider
from .pipeline import run_pipeline
from .providers import FixtureAnalysisProvider, FixtureTranscriptProvider


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


def main() -> None:
    args = _parser().parse_args()
    if args.command == "run-fixture":
        try:
            _run_fixture(args)
        except BackendUnavailableError as error:
            # A configuration failure, not a crash. The message names what is missing
            # and never the value of anything.
            raise SystemExit(f"analysis backend unavailable: {error}") from error
        except BackendError as error:
            raise SystemExit(f"analysis backend failed: {error}") from error


if __name__ == "__main__":
    main()
