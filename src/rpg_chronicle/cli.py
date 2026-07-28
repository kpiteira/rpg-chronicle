"""Command line entry point.

Provider selection lives here and only here. `pipeline.py` receives constructed
providers and never learns which kind it was handed, so pointing the slice at a real
model is a wiring change in this file, exactly as `docs/DECISIONS.md` D-008 promised.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from .analysis.backend import BackendError, BackendUnavailableError
from .analysis.claude_cli import DEFAULT_MODEL, ClaudeCliBackend
from .analysis.decompose import TokenBudget
from .analysis.prompts import ApprovedName
from .analysis.provider import DEFAULT_MAX_QUESTIONS, ModelAnalysisProvider
from .pipeline import load_session, run_pipeline
from .providers import FixtureAnalysisProvider, FixtureTranscriptProvider
from .review.answers import CARRY_FORWARD_ACTION, AnswerError, load_answer_sheet
from .review.console import Console, ReviewAborted, collect_answers
from .review.record import RECORD_FILENAME, CorrectionRecord, UnreadableRecordError
from .review.session import CANONICAL_FILENAME, answer_session
from .review.vocabulary import STORE_FILENAME, Vocabulary, VocabularyError
from .transcription.engine import EngineError, EngineUnavailableError
from .transcription.name_uncertainty import DEFAULT_RARITY_FLOOR, WordfreqLexicon
from .transcription.provider import SpeechTranscriptProvider
from .transcription.sherpa_diarization import (
    DEFAULT_CLUSTER_THRESHOLD,
    SherpaDiarizationEngine,
)
from .transcription.whisper_cpp import DEFAULT_MODEL_FILENAME, WhisperCppEngine
from .vault.digest import vault_digest
from .vault.survey import format_report, survey_vault

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
    _add_vocabulary_flags(run_fixture)

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
        "--no-name-uncertainty",
        action="store_true",
        help=(
            "skip the name-uncertainty pass. It costs milliseconds against minutes of "
            "recognition, so the reason to skip it is not having the lexicon installed."
        ),
    )
    run_audio.add_argument(
        "--rarity-floor",
        type=float,
        default=DEFAULT_RARITY_FLOOR,
        help=(
            "Zipf frequency below which a word is a name candidate. Raising it finds "
            "more mangled names and adds ordinary rare vocabulary to the queue: measured "
            "on the benchmark recording, 3.0 caught one more verified name and tripled "
            "the queue. See research/name-uncertainty.md."
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
    _add_vocabulary_flags(run_audio)

    review = subparsers.add_parser(
        "review",
        help="answer the questions in a session's review package",
        description=(
            "Walks the needs-attention queue and applies what you decide to the canonical "
            "session. Nothing is written until the whole sheet applies, an answer's effect "
            "is recorded in corrections.json with what it changed from, and an approved "
            "name joins the vocabulary so the next session does not ask again."
        ),
    )
    review.add_argument("session_dir", type=Path, help="a session directory the pipeline wrote")
    review.add_argument(
        "--answers",
        type=Path,
        help=(
            "a JSON answer sheet, instead of the interactive queue. Same effect, "
            "scriptable, and what the acceptance evidence uses."
        ),
    )
    review.add_argument(
        "--by",
        default="operator",
        help="who is answering; recorded against every answer and every approved name",
    )
    review.add_argument(
        "--vocabulary",
        type=Path,
        help="approved-name store (default: vocabulary.json beside the session directories)",
    )
    review.add_argument(
        "--include-answered",
        action="store_true",
        help="show questions that already carry a disposition, not only open ones",
    )
    review.add_argument(
        "--override",
        action="store_true",
        help=(
            "record a disagreement with somebody else's earlier decision and supersede "
            "it. Without this, an answer that would change what another person settled "
            "is refused and nothing is written. The earlier decision survives in "
            "corrections.json either way."
        ),
    )
    review.add_argument(
        "--dry-run",
        action="store_true",
        help="report what the answers would change and write nothing",
    )

    score = subparsers.add_parser(
        "score",
        help="score a completed run against a benchmark manifest",
        description=(
            "Reports every dimension docs/MILESTONES.md makes M2 conditional on, each "
            "with the basis it was computed from -- or with a statement that it cannot "
            "be measured yet and precisely what is missing. It never improves a score "
            "and never touches the run. Manifests and answer keys live in the content "
            "directory (~/.rpg-chronicle, RPG_CHRONICLE_HOME to override), not in this "
            "repository, so --manifest takes a manifest id or a path to one."
        ),
    )
    score.add_argument(
        "--session",
        type=Path,
        required=True,
        help="a session directory a pipeline run wrote, which is <output>/<session-id>",
    )
    score.add_argument(
        "--manifest",
        required=True,
        help="manifest id in the content directory, or a path to a manifest file",
    )
    score.add_argument(
        "--run-report",
        type=Path,
        help=(
            "the JSON `run-audio --run-report` wrote for this run. Time and memory are "
            "measured during the run and cannot be recovered from a session afterwards; "
            "without this they are reported unmeasurable rather than guessed."
        ),
    )
    score.add_argument(
        "--report",
        type=Path,
        help=(
            "write the full JSON report here. It quotes truth labels, so it belongs in "
            "the content directory beside the manifest and never in this repository."
        ),
    )

    vault_survey = subparsers.add_parser(
        "vault-survey",
        help="walk a vault read-only and report its structure",
        description=(
            "Reports note types, frontmatter keys, link topology and section "
            "conventions. It opens files and never writes them. The report echoes the "
            "vault's own section titles, so the output of a run against a real vault is "
            "a description of that vault: keep it outside the repository, beside the "
            "recordings. See docs/VAULT_INTEGRATION.md."
        ),
    )
    vault_survey.add_argument("vault", type=Path)
    vault_survey.add_argument(
        "--json",
        type=Path,
        help="also write the counted findings as JSON to this path",
    )

    vault_integrity = subparsers.add_parser(
        "vault-digest",
        help="fingerprint a vault so a later change would be detectable",
        description=(
            "Prints a file count, a total size, the newest modification time and one "
            "rolled-up SHA-256 over every file's path and contents. It names nothing "
            "inside the vault, so the output is safe to publish as evidence that a "
            "read-only promise was kept. Obsidian's configuration directory and the "
            "operating system's own scratch files are excluded by default, because both "
            "are rewritten merely by looking at the vault."
        ),
    )
    vault_integrity.add_argument("vault", type=Path)
    vault_integrity.add_argument(
        "--include-app-state",
        action="store_true",
        help=(
            "cover .obsidian, .trash and .DS_Store too; only meaningful with the vault "
            "closed and unopened in a file browser"
        ),
    )
    return parser


def _add_vocabulary_flags(subparser: argparse.ArgumentParser) -> None:
    """Where approved names come from, for the commands that produce entities.

    Carrying forward is on by default because a store nothing reads improves nothing,
    which is the half of `docs/PRODUCT.md`'s "improve from approved vocabulary" that
    usually gets deferred. Every application is recorded in the session's own correction
    record, so the default is visible rather than silent, and `--no-carry-forward` turns
    it off for a run that must reproduce what the analysis alone produced.
    """
    subparser.add_argument(
        "--vocabulary",
        type=Path,
        help="approved-name store (default: vocabulary.json in the output directory)",
    )
    subparser.add_argument(
        "--no-carry-forward",
        action="store_true",
        help="ignore approved names entirely; report the analysis exactly as produced",
    )


def _vocabulary_for(args: argparse.Namespace) -> Vocabulary | None:
    if args.no_carry_forward:
        return None
    path = args.vocabulary or (args.output / STORE_FILENAME)
    try:
        return Vocabulary.load(path)
    except VocabularyError as error:
        raise SystemExit(f"vocabulary unusable: {error}") from error
    except UnreadableRecordError as error:
        raise SystemExit(f"correction record unusable: {error}") from error


def _report_carry_forward(session_dir: Path, session_id: str) -> None:
    record_path = session_dir / RECORD_FILENAME
    if not record_path.exists():
        return
    record = CorrectionRecord.load(record_path, session_id=session_id)
    carried = [entry for entry in record.entries if entry.action == CARRY_FORWARD_ACTION]
    applied = [entry for entry in carried if entry.changes]
    if applied:
        print(f"carried forward: {len(applied)} approved name(s) applied")
        for entry in applied:
            for change in entry.changes:
                before = (change.before or {})["entities"][0]["name"]
                after = (change.after or {})["entities"][0]["name"]
                print(f"  {change.target}: {before!r} -> {after!r}")
    for entry in carried:
        if entry.declined:
            print(f"carry-forward declined for {entry.note}: {entry.declined}")


def _score(args: argparse.Namespace) -> None:
    from .scoring import (
        ManifestNotFoundError,
        SessionNotFoundError,
        load_manifest,
        load_session,
        render,
        render_json,
    )
    from .scoring import score as score_run

    try:
        manifest = load_manifest(args.manifest)
        session_dir = args.session.expanduser().resolve()
        session = load_session(session_dir)
    except (ManifestNotFoundError, SessionNotFoundError) as error:
        raise SystemExit(str(error)) from error

    run_report = None
    if args.run_report:
        run_report = json.loads(args.run_report.read_text())

    report = score_run(manifest, session_dir, session, run_report)
    print(render(report), end="")
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(render_json(report))
        print(f"report: {args.report}")
    # A withheld verdict is a refusal, and a refusal that exits 0 is one a script will
    # step over. The dimensions are still printed -- the operator asked for them and the
    # clean ones are valid -- but the exit status says the headline score was not given.
    if report["verdict"] != "reported":
        raise SystemExit(2)


def approved_names(vocabulary: Vocabulary | None) -> tuple[ApprovedName, ...]:
    """The settled names worth telling a model about.

    Contested entries are left out. Two people disagreeing about a spelling is not
    something to put in a prompt as though it were decided, and the model's guess is the
    one input that cannot settle it.
    """
    if vocabulary is None:
        return ()
    return tuple(
        ApprovedName(canonical=entry.canonical, kind=entry.kind, aliases=tuple(entry.aliases))
        for entry in vocabulary.entries
        if not entry.contested
    )


def _vault_survey(args: argparse.Namespace) -> None:
    # Handled here rather than in `main()`. Rule 4 of docs/PARALLEL_EXECUTION.md lets a
    # role add its own wiring to this file; a shared `except` clause would have changed
    # the error path of every other role's command too, which is the other half of the
    # rule.
    try:
        survey = survey_vault(args.vault)
    except NotADirectoryError as error:
        raise SystemExit(str(error)) from error
    print(format_report(survey), end="")
    if args.json:
        topology = survey.link_topology()
        payload = {
            "notes": len(survey.notes),
            "note_types": dict(survey.note_types()),
            "folders": dict(survey.folders()),
            "frontmatter_keys": dict(survey.frontmatter_keys()),
            "inconsistent_value_shapes": survey.inconsistent_value_shapes(),
            "link_topology": {
                "total": topology.total,
                "distinct_targets": topology.distinct_targets,
                "resolved": topology.resolved,
                "unresolved": topology.unresolved,
                "ambiguous": topology.ambiguous,
                "piped": topology.piped,
                "anchored": topology.anchored,
                "path_qualified": topology.path_qualified,
                "embeds_to_asset": topology.embeds_to_asset,
                "embeds_to_note": topology.embeds_to_note,
            },
            "accumulating_notes": len(survey.accumulating_notes()),
            "accumulation_positions": dict(survey.accumulation_positions()),
            "stub_notes": len(survey.stubs()),
            "ambiguous_titles": len(survey.ambiguous_titles()),
            "provenance_signals": list(survey.provenance_signals()),
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(f"json: {args.json}")


def _vault_digest(args: argparse.Namespace) -> None:
    try:
        if args.include_app_state:
            print(
                vault_digest(
                    args.vault,
                    ignored_directories=frozenset(),
                    ignored_filenames=frozenset(),
                )
            )
            return
        print(vault_digest(args.vault))
    except NotADirectoryError as error:
        raise SystemExit(str(error)) from error


def _model_provider(
    args: argparse.Namespace, vocabulary: Vocabulary | None = None
) -> ModelAnalysisProvider:
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
        approved_names=approved_names(vocabulary),
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
    # Loaded once and used twice: settled names go into the prompt so the model spells
    # them right in the first place, and into the pipeline so an entity it still spells
    # the old way is corrected deterministically afterwards. The two are not redundant --
    # the first only works with a model, the second works with any provider.
    vocabulary = _vocabulary_for(args)

    if args.analysis == "model":
        try:
            provider: FixtureAnalysisProvider | ModelAnalysisProvider = _model_provider(
                args, vocabulary
            )
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
        vocabulary=vocabulary,
    )

    print(f"{session.session_id}: {session.status}")
    _report_carry_forward(args.output / session.session_id, session.session_id)
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
    lexicon = None if args.no_name_uncertainty else WordfreqLexicon()
    return SpeechTranscriptProvider(
        recognizer, diarizer, lexicon=lexicon, rarity_floor=args.rarity_floor
    )


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
        # Counts, never the spellings. The candidates themselves are recognized tokens
        # from the recording and stay in the engine-native artifact outside the
        # repository; what belongs in committable evidence is how many there were and
        # how many the engine contradicted itself about.
        **_name_uncertainty_counts(session, args.output),
        "processor_artifacts": dict(native),
        "contains_recognized_text": False,
    }


def _name_uncertainty_counts(session: Any, output: Path) -> dict:
    """Read the name-uncertainty summary back out of the engine-native artifact.

    Reported here because a figure that lives only in prose is not evidence -- the same
    complaint #23 carried forward about its own write-up. A resumed run reads the
    artifact the original run wrote, so the counts survive the transcription stage being
    skipped.
    """
    relative = session.processor_artifacts.get("transcript")
    if not relative:
        return {}
    path = output / session.session_id / relative
    try:
        block = json.loads(path.read_text()).get("name_uncertainty", {})
    except (OSError, ValueError):
        return {}
    if not block.get("computed"):
        return {"name_candidates": None, "name_uncertainty_skipped": block.get("why_not")}
    return {
        "name_candidates": block.get("candidates"),
        "name_candidates_self_contradicted": block.get("self_contradicted"),
        "name_uncertainty_lexicon": block.get("lexicon"),
        "name_uncertainty_rarity_floor": block.get("rarity_floor"),
    }


def _run_audio(args: argparse.Namespace) -> None:
    vocabulary = _vocabulary_for(args)
    if args.analysis == "model":
        try:
            analysis: FixtureAnalysisProvider | ModelAnalysisProvider = _model_provider(
                args, vocabulary
            )
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
        vocabulary=vocabulary,
    )
    wall_s = time.monotonic() - started

    print(f"{session.session_id}: {session.status}")
    _report_carry_forward(args.output / session.session_id, session.session_id)
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


def _review(args: argparse.Namespace) -> None:
    canonical = args.session_dir / CANONICAL_FILENAME
    if not canonical.exists():
        raise SystemExit(
            f"{canonical} does not exist. Point this at a session directory the pipeline "
            "has carried to review_ready."
        )

    if args.answers:
        sheet = load_answer_sheet(args.answers, default_answered_by=args.by)
    else:
        sheet = collect_answers(
            load_session(canonical),
            console=Console(stdin=sys.stdin, stdout=sys.stdout),
            answered_by=args.by,
            include_answered=args.include_answered,
        )

    if not sheet.answers:
        print("nothing was answered; the session is unchanged")
        return

    reviewed = answer_session(
        args.session_dir,
        sheet,
        vocabulary_path=args.vocabulary,
        override=args.override,
        dry_run=args.dry_run,
    )
    outcome = reviewed.outcome
    prefix = "would change" if args.dry_run else "changed"
    print(
        f"{reviewed.session.session_id}: {len(outcome.applied)} answered, "
        f"{len(outcome.changed_entities)} entity record(s) {prefix}"
    )
    for entry in reviewed.record.entries[-len(sheet.answers) :]:
        line = f"  {entry.question_id}: {entry.action}"
        for change in entry.changes:
            before = (change.before or {})["entities"]
            after = (change.after or {})["entities"][0]
            names = ", ".join(repr(item["name"]) for item in before)
            line += f" -- {change.operation} {names} -> {after['name']!r}"
        print(line)
    if outcome.vocabulary_entries:
        verb = "would join" if args.dry_run else "joined"
        print(
            f"vocabulary: {len(outcome.vocabulary_entries)} name(s) {verb} "
            f"{reviewed.vocabulary_path}"
        )
    if args.dry_run:
        print("dry run: nothing was written")
    else:
        print(f"record: {args.session_dir / RECORD_FILENAME}")


def main() -> None:
    args = _parser().parse_args()
    handlers = {
        "run-fixture": _run_fixture,
        "run-audio": _run_audio,
        "review": _review,
        "score": _score,
        "vault-survey": _vault_survey,
        "vault-digest": _vault_digest,
    }
    try:
        handlers[args.command](args)
    except AnswerError as error:
        # A refused sheet changed nothing, so this is a usage error rather than a crash.
        raise SystemExit(f"answers refused: {error}") from error
    except ReviewAborted as error:
        raise SystemExit(f"review stopped: {error}; nothing was written") from error
    except VocabularyError as error:
        raise SystemExit(f"vocabulary unusable: {error}") from error
    except UnreadableRecordError as error:
        raise SystemExit(f"correction record unusable: {error}") from error
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
