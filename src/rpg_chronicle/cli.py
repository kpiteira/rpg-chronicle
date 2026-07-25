"""Command line entry point."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .pipeline import run_pipeline
from .providers import FixtureAnalysisProvider, FixtureTranscriptProvider


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rpg-chronicle")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_fixture = subparsers.add_parser("run-fixture", help="run the synthetic vertical slice")
    run_fixture.add_argument("fixture", type=Path)
    run_fixture.add_argument("--output", type=Path, required=True)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "run-fixture":
        session_id = json.loads(args.fixture.read_text())["session"]["id"]
        session = run_pipeline(
            source=args.fixture,
            output_dir=args.output,
            transcript_provider=FixtureTranscriptProvider(),
            analysis_provider=FixtureAnalysisProvider(args.fixture),
            session_id=session_id,
        )
        print(f"{session.session_id}: {session.status}")
        print("analysis provider: fixture (declared truth, not model output)")


if __name__ == "__main__":
    main()
