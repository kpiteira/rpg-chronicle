"""Scoring one completed run against one benchmark manifest.

`docs/MILESTONES.md` makes M2 conditional on evaluation that "measures plot/entity
capture, unsupported claims, surfaced errors, time, memory, question count, and review
burden". This module computes those, and -- for the ones it cannot compute -- says so and
names the input that is missing. `docs/EVALUATION.md` holds the reader-facing description
of what each number does and does not mean.

Two rules shape everything here.

*A number with no stated basis is worse than no number.* Every dimension carries the
thing it was computed from and the provenance of the truth behind it, and the report is
built so that a value cannot be read without them.

*Partial coverage stated plainly beats seven numbers of mixed integrity.* An unmeasurable
dimension is a first-class outcome with a named missing input, not a zero.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from . import contamination
from .manifest import Manifest
from .match import Span, TargetOutcome, label_matches, mentions, normalize

HARNESS_VERSION = "0.1"

#: The share of a truth event's distinctive words that must appear in the scene covering
#: its anchor before the scene is counted as corroborating the event's content. A chosen
#: constant, not a calibrated one: nothing here has been fitted against human judgement of
#: whether a scene describes an event, and the report says so wherever this is used.
TERM_OVERLAP_FLOOR = 0.5

#: Tokens too short to distinguish one event from another.
MIN_DISTINCTIVE_CHARS = 4

#: Assumed review costs, used only by the review-burden proxy. Neither has been measured.
#: `docs/PRODUCT.md` sets the target these are compared against -- under three minutes of
#: review per recorded hour at personal alpha -- but it says nothing about how long one
#: question takes to answer, and no run has been timed. Until one is, this dimension is a
#: proxy with declared constants and is reported as a proxy.
ASSUMED_SECONDS_PER_QUESTION = 45
ASSUMED_SECONDS_PER_SCENE = 20
REVIEW_BURDEN_TARGET_SECONDS_PER_HOUR = 180


class SessionNotFoundError(FileNotFoundError):
    """Raised when the session directory holds no canonical session."""


@dataclass(frozen=True)
class Dimension:
    """One measured thing, or one honest refusal to measure it.

    `basis` and `caveat` are not decoration. A dimension serialises with both, so a reader
    who pulls a single number out of the JSON has to walk past what produced it and what
    it does not mean.
    """

    name: str
    criterion: str
    measured: bool
    basis: str
    caveat: str
    value: dict[str, Any] = field(default_factory=dict)
    missing: str | None = None
    contaminated: bool = False
    withheld_because: str | None = None

    @property
    def reportable(self) -> bool:
        return self.measured and not self.contaminated

    def to_dict(self) -> dict[str, Any]:
        """Serialise, dropping the fields that do not apply to this dimension's state.

        A contaminated dimension loses its `value` outright rather than carrying it under
        a flag. The number was computed -- the harness had to compute it to know the
        comparison was possible at all -- and publishing it beside a warning would leave a
        quotable figure in the file, which is the whole failure the contamination rule
        exists to prevent. What survives is the basis, the caveat, and why it is gone.
        """
        payload = asdict(self)
        if not self.measured:
            payload.pop("value")
            payload.pop("withheld_because")
            return payload
        payload.pop("missing")
        if self.contaminated:
            payload.pop("value")
        else:
            payload.pop("withheld_because")
        return payload


def load_session(session_dir: Path) -> dict[str, Any]:
    """Read a completed run's canonical session as plain JSON.

    Deliberately not through `pipeline._load_session`. A scoring tool must be able to
    report on a session it cannot fully construct -- that is a finding about the run, not
    a crash -- and constructing the dataclasses would turn a bad field into a traceback
    from three modules down.
    """
    path = session_dir / "canonical-session.json"
    if not path.is_file():
        raise SessionNotFoundError(
            f"{path} does not exist. Point --session at a directory a pipeline run wrote, "
            "which is <output>/<session-id>."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _evidence_span(item: dict[str, Any]) -> Span | None:
    evidence = item.get("evidence") or {}
    start, end = evidence.get("start_ms"), evidence.get("end_ms")
    if start is None or end is None:
        return None
    return Span(int(start), int(end))


def _claim_texts(session: dict[str, Any]) -> list[tuple[str, str]]:
    """Everything the run asserts, paired with where it asserted it.

    Transcript turns are excluded on purpose. A turn is what a recognizer heard; a claim
    is what the chronicle tells the operator. The unsupported-claim dimension is about the
    second, and the report keeps the first as a separate signal so that a recognizer's
    invention is never confused with the analysis's.
    """
    texts: list[tuple[str, str]] = []
    if session.get("summary"):
        texts.append(("summary", str(session["summary"])))
    for scene in session.get("scenes") or []:
        texts.append((f"scene:{scene.get('id')}", f"{scene.get('title', '')} {scene.get('summary', '')}"))
    for entity in session.get("entities") or []:
        names = " ".join([str(entity.get("name", ""))] + [str(a) for a in entity.get("aliases") or []])
        texts.append((f"entity:{entity.get('id')}", names))
    for thread in session.get("threads") or []:
        texts.append((f"thread:{thread.get('id')}", str(thread.get("description", ""))))
    for question in session.get("review_questions") or []:
        joined = " ".join(
            str(question.get(key, "") or "")
            for key in ("issue", "recommendation", "why_it_matters", "consequence")
        )
        texts.append((f"question:{question.get('id')}", joined))
    return texts


@dataclass(frozen=True)
class TimeBasis:
    """How manifest anchors line up with the session's clock, and whether they do.

    A manifest anchor is an offset into the published media. A session's turns are offsets
    into whatever file was fed to the recognizer. Those agree when the whole episode was
    processed and differ by the excerpt start when a clip was. Guessing wrong would make
    every anchor-based dimension report a confident zero, so the alignment is chosen by
    which hypothesis actually lands anchors inside the session, and reported.
    """

    offset_ms: int
    hypothesis: str
    anchors_inside: int
    anchors_total: int
    session_span: tuple[int, int] | None

    @property
    def aligned(self) -> bool:
        return self.anchors_total == 0 or self.anchors_inside > 0

    def align(self, anchor_ms: int) -> int:
        return anchor_ms - self.offset_ms


def time_basis(session: dict[str, Any], manifest: Manifest) -> TimeBasis:
    turns = session.get("turns") or []
    anchors = [t.anchor_ms for t in manifest.targets if t.anchor_ms is not None]
    if not turns:
        return TimeBasis(0, "media_offsets (no turns to check against)", 0, len(anchors), None)

    span = (
        min(int(turn["start_ms"]) for turn in turns),
        max(int(turn["end_ms"]) for turn in turns),
    )
    excerpt_start, _ = manifest.excerpt_ms

    def inside(offset: int) -> int:
        return sum(1 for anchor in anchors if span[0] <= anchor - offset <= span[1])

    candidates = [(0, "media_offsets"), (excerpt_start, "excerpt_relative")]
    offset, hypothesis = max(candidates, key=lambda item: inside(item[0]))
    return TimeBasis(offset, hypothesis, inside(offset), len(anchors), span)


def _target_outcomes(
    manifest: Manifest,
    session: dict[str, Any],
    basis: TimeBasis,
) -> list[TargetOutcome]:
    entities = session.get("entities") or []
    outcomes: list[TargetOutcome] = []
    for target in manifest.targets:
        if not target.is_entity:
            continue
        matched_names: list[str] = []
        corroborated = False
        for entity in entities:
            candidates = [str(entity.get("name", ""))] + [
                str(alias) for alias in entity.get("aliases") or []
            ]
            hit = next((c for c in candidates if label_matches(target.label, c)), None)
            if hit is None:
                continue
            matched_names.append(hit)
            span = _evidence_span(entity)
            if target.anchor_ms is not None and span and span.covers(basis.align(target.anchor_ms)):
                corroborated = True
        outcomes.append(
            TargetOutcome(
                path=target.path,
                label=target.label,
                kind=target.kind,
                status=target.status,
                basis=target.basis,
                anchor_ms=target.anchor_ms,
                matched_by_name=bool(matched_names),
                anchor_corroborated=corroborated,
                matched_names=matched_names,
            )
        )
    return outcomes


def _share(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _by_basis(outcomes: list[TargetOutcome]) -> dict[str, dict[str, Any]]:
    """Recall split by how the truth behind each target was established.

    One number over a mixed answer key hides the thing most worth knowing. Matching four
    targets somebody read off a web page is not the same achievement as matching four
    somebody heard, and averaging them produces a figure that describes neither.
    """
    groups: dict[str, dict[str, Any]] = {}
    for outcome in outcomes:
        key = outcome.basis or "unstated"
        bucket = groups.setdefault(key, {"targets": 0, "matched_by_name": 0, "anchor_corroborated": 0})
        bucket["targets"] += 1
        bucket["matched_by_name"] += int(outcome.matched_by_name)
        bucket["anchor_corroborated"] += int(outcome.anchor_corroborated)
    for bucket in groups.values():
        bucket["recall_by_name"] = _share(bucket["matched_by_name"], bucket["targets"])
    return groups


def entity_capture(
    manifest: Manifest,
    session: dict[str, Any],
    basis: TimeBasis,
    outcomes: list[TargetOutcome],
) -> Dimension:
    if not outcomes:
        return Dimension(
            name="entity_capture",
            criterion="plot/entity capture",
            measured=False,
            basis="none",
            caveat="",
            missing=(
                f"{manifest.path.name} declares no truth.important_entities. An entity "
                "recall needs an annotated answer key; this manifest has not been "
                "annotated, and annotating it is a separate goal"
            ),
        )
    if not (session.get("entities") or []):
        return Dimension(
            name="entity_capture",
            criterion="plot/entity capture",
            measured=True,
            basis=(
                f"{len(outcomes)} annotated entity targets against 0 entities in the "
                "session; the run produced no entities at all"
            ),
            caveat=(
                "a recall of zero here is a fact about the run, not about the analysis "
                "provider's ability: a fixture provider with no declared entities and a "
                "model that found none are indistinguishable in this number"
            ),
            value={
                "targets": len(outcomes),
                "session_entities": 0,
                "matched_by_name": 0,
                "recall_by_name": 0.0,
                "anchor_corroborated": 0,
                "recall_anchor_corroborated": 0.0,
                "by_basis": _by_basis(outcomes),
            },
        )

    matched = sum(1 for outcome in outcomes if outcome.matched_by_name)
    corroborated = sum(1 for outcome in outcomes if outcome.anchor_corroborated)
    anchored = sum(1 for outcome in outcomes if outcome.anchor_ms is not None)
    return Dimension(
        name="entity_capture",
        criterion="plot/entity capture",
        measured=True,
        basis=(
            f"{len(outcomes)} annotated entity targets from {manifest.path.name} against "
            f"{len(session.get('entities') or [])} entities the run produced. A target "
            "counts as matched by name when the entity's name or one of its aliases "
            "occurs inside the target's label as whole words, or the label occurs inside "
            f"the name. Anchors were read on the {basis.hypothesis} hypothesis"
        ),
        caveat=(
            "recall_by_name is an upper bound: it establishes that the run produced the "
            "name, not that it produced it as the thing the annotator heard. "
            "recall_anchor_corroborated is the matching lower bound -- the name was "
            f"produced citing turns that span the annotated moment -- computed over the "
            f"{anchored} targets that carry an anchor. The true figure is between them, "
            "and no judge has been run to narrow it. Neither number says the entity was "
            "described correctly; both say only that the name was found"
        ),
        value={
            "targets": len(outcomes),
            "session_entities": len(session.get("entities") or []),
            "matched_by_name": matched,
            "recall_by_name": _share(matched, len(outcomes)),
            "anchored_targets": anchored,
            "anchor_corroborated": corroborated,
            "recall_anchor_corroborated": _share(corroborated, len(outcomes)),
            "by_basis": _by_basis(outcomes),
            "missed_targets": [outcome.path for outcome in outcomes if outcome.missed],
        },
    )


def _distinctive(label: str) -> list[str]:
    return [token for token in normalize(label) if len(token) >= MIN_DISTINCTIVE_CHARS]


def plot_capture(
    manifest: Manifest,
    session: dict[str, Any],
    basis: TimeBasis,
) -> Dimension:
    events = [target for target in manifest.targets if not target.is_entity]
    if not events:
        return Dimension(
            name="plot_capture",
            criterion="plot/entity capture",
            measured=False,
            basis="none",
            caveat="",
            missing=(
                f"{manifest.path.name} declares no truth.important_events, so there is "
                "nothing to score plot capture against"
            ),
        )
    anchored = [event for event in events if event.anchor_ms is not None]
    if not anchored:
        return Dimension(
            name="plot_capture",
            criterion="plot/entity capture",
            measured=False,
            basis="none",
            caveat="",
            missing=(
                f"none of the {len(events)} event targets in {manifest.path.name} carries "
                "an anchor_ms. Event labels are sentences, so they cannot be matched "
                "lexically; anchor coverage is the only mechanical handle, and it needs "
                "an anchor"
            ),
        )
    if not basis.aligned:
        return Dimension(
            name="plot_capture",
            criterion="plot/entity capture",
            measured=False,
            basis="none",
            caveat="",
            missing=(
                f"no annotated anchor falls inside the session's turn span "
                f"{basis.session_span}, on either the media-offset or the "
                "excerpt-relative hypothesis. The session and the manifest are not "
                "describing the same span of audio, and a coverage figure computed across "
                "that mismatch would be a confident zero rather than a measurement"
            ),
        )

    scenes = session.get("scenes") or []
    covered = 0
    corroborated = 0
    uncovered: list[str] = []
    for event in anchored:
        anchor = basis.align(event.anchor_ms)  # type: ignore[arg-type]
        covering = [
            scene
            for scene in scenes
            if (span := _evidence_span(scene)) is not None and span.covers(anchor)
        ]
        if not covering:
            uncovered.append(event.path)
            continue
        covered += 1
        wanted = _distinctive(event.label)
        if not wanted:
            continue
        best = max(
            (
                sum(1 for token in wanted if token in set(normalize(
                    f"{scene.get('title', '')} {scene.get('summary', '')}"
                )))
                / len(wanted)
            )
            for scene in covering
        )
        if best >= TERM_OVERLAP_FLOOR:
            corroborated += 1

    return Dimension(
        name="plot_capture",
        criterion="plot/entity capture",
        measured=True,
        basis=(
            f"{len(anchored)} anchored event targets from {manifest.path.name} against "
            f"{len(scenes)} scenes. An event is covered when some scene's evidence span "
            f"contains its anchor, read on the {basis.hypothesis} hypothesis "
            f"({basis.anchors_inside} of {basis.anchors_total} anchors land inside the "
            "session's turns)"
        ),
        caveat=(
            "anchor coverage is an upper bound on plot capture and nothing more. A scene "
            "spanning the annotated moment may describe something else entirely; this "
            "harness does not read the scene and decide. term_overlap counts covering "
            "scenes that also repeat at least "
            f"{int(TERM_OVERLAP_FLOOR * 100)}% of the event label's distinctive words -- a "
            "weak corroboration with a chosen threshold that has never been calibrated "
            "against human judgement, and which a differently worded correct summary "
            "fails. Deciding capture properly needs a judge, and a judge would make this "
            "instrument move when the judge is upgraded"
        ),
        value={
            "events": len(events),
            "anchored_events": len(anchored),
            "scenes": len(scenes),
            "anchor_covered": covered,
            "coverage_upper_bound": _share(covered, len(anchored)),
            "covered_with_term_overlap": corroborated,
            "term_overlap_share": _share(corroborated, len(anchored)),
            "uncovered_targets": uncovered,
        },
    )


def unsupported_claims(
    manifest: Manifest,
    session: dict[str, Any],
) -> Dimension:
    claims = _claim_texts(session)
    turn_text = " ".join(str(turn.get("text", "")) for turn in session.get("turns") or [])
    turn_ids = {str(turn.get("id")) for turn in session.get("turns") or []}

    control_findings = []
    for control in manifest.negative_controls:
        asserted_in = [where for where, text in claims if mentions(text, control.term)]
        control_findings.append(
            {
                "term": control.term,
                "kind": control.kind,
                "asserted_in": asserted_in,
                "in_transcript": mentions(turn_text, control.term),
                "rationale": control.rationale,
            }
        )

    # An entity whose name occurs in none of the turns it cites was not read off the
    # transcript. This needs no answer key at all, which makes it the one unsupported-claim
    # signal available on every session including ones with no annotated manifest.
    fabricated = []
    turns_by_id = {str(turn.get("id")): str(turn.get("text", "")) for turn in session.get("turns") or []}
    for entity in session.get("entities") or []:
        cited = " ".join(
            turns_by_id.get(str(turn_id), "")
            for turn_id in (entity.get("evidence") or {}).get("turn_ids") or []
        )
        candidates = [str(entity.get("name", ""))] + [
            str(alias) for alias in entity.get("aliases") or []
        ]
        if cited and not any(mentions(cited, candidate) for candidate in candidates):
            fabricated.append({"id": entity.get("id"), "name": entity.get("name")})

    dangling = 0
    for group in ("scenes", "review_questions", "entities", "threads"):
        for item in session.get(group) or []:
            cited_ids = (item.get("evidence") or {}).get("turn_ids") or []
            dangling += sum(1 for turn_id in cited_ids if str(turn_id) not in turn_ids)

    hits = sum(1 for finding in control_findings if finding["asserted_in"])
    return Dimension(
        name="unsupported_claims",
        criterion="unsupported claims",
        measured=True,
        basis=(
            f"{len(manifest.negative_controls)} declared negative controls searched across "
            f"{len(claims)} claim texts; {len(session.get('entities') or [])} entities "
            "checked against the text of the turns each one cites; evidence citations "
            f"checked against {len(turn_ids)} turn ids"
        ),
        caveat=(
            "this counts three specific, mechanical failures and is not a complete census "
            "of unsupported claims. A negative control fires only for terms an annotator "
            "established are absent, and this manifest declares "
            f"{len(manifest.negative_controls)}. `in_transcript` separates an analysis "
            "that invented a term from one that faithfully repeated a recognizer's "
            "invention -- the second is a recognition failure and is not scored here. "
            "claims_citing_missing_turns is normally zero by construction, because "
            "`model.evidence_for` refuses such a claim at build time; a non-zero value "
            "means a session was written by something that bypassed it"
        ),
        value={
            "negative_controls": len(manifest.negative_controls),
            "negative_control_hits": hits,
            "findings": control_findings,
            "entities_absent_from_cited_turns": len(fabricated),
            "fabricated_entities": fabricated,
            "claims_citing_missing_turns": dangling,
        },
    )


def surfaced_errors(
    session: dict[str, Any],
    basis: TimeBasis,
    outcomes: list[TargetOutcome],
    unsupported: Dimension,
) -> Dimension:
    """Of the things this run got wrong, how many did it raise a question about.

    `docs/EVALUATION.md` lists "important errors not surfaced" as a dimension, and this is
    the executable reading of it: an error the harness can see, cross-referenced against
    the review queue. A miss the run asked about is a system behaving well under
    uncertainty; a miss it said nothing about is the failure mode M4 names as warned or
    withheld.
    """
    questions = session.get("review_questions") or []
    if not outcomes and not unsupported.value.get("findings"):
        return Dimension(
            name="surfaced_errors",
            criterion="surfaced errors",
            measured=False,
            basis="none",
            caveat="",
            missing=(
                "the manifest supplies neither entity targets nor negative controls, so "
                "the harness sees no errors to ask whether the run surfaced"
            ),
        )

    question_spans = [
        span for question in questions if (span := _evidence_span(question)) is not None
    ]
    question_text = " ".join(
        " ".join(str(question.get(key, "") or "") for key in ("issue", "recommendation", "why_it_matters"))
        for question in questions
    )

    missed_anchored = [
        outcome for outcome in outcomes if outcome.missed and outcome.anchor_ms is not None
    ]
    surfaced = [
        outcome
        for outcome in missed_anchored
        if any(span.covers(basis.align(outcome.anchor_ms)) for span in question_spans)  # type: ignore[arg-type]
    ]

    control_hits = [
        finding for finding in unsupported.value.get("findings", []) if finding["asserted_in"]
    ]
    controls_flagged = [
        finding for finding in control_hits if mentions(question_text, finding["term"])
    ]

    errors = len(missed_anchored) + len(control_hits)
    caught = len(surfaced) + len(controls_flagged)
    return Dimension(
        name="surfaced_errors",
        criterion="surfaced errors",
        measured=True,
        basis=(
            f"{len(missed_anchored)} anchored entity targets the run missed and "
            f"{len(control_hits)} negative-control assertions, cross-referenced against "
            f"{len(questions)} review questions. A miss counts as surfaced when some "
            "question's evidence span contains the missed target's anchor; a control "
            "assertion counts as surfaced when a question names the term"
        ),
        caveat=(
            "this measures only errors the harness itself detected, so it inherits every "
            "bound above it: an entity capture upper bound means some 'misses' are "
            "matching failures of the instrument, and a question covering an anchor need "
            "not be a question about that target. It is silent about the largest class of "
            "important errors -- a scene that confidently describes the wrong thing -- "
            "because nothing here detects one"
        ),
        value={
            "detected_errors": errors,
            "surfaced": caught,
            "unsurfaced": errors - caught,
            "surfaced_share": _share(caught, errors),
            "review_questions": len(questions),
            "questions_carrying_evidence_spans": len(question_spans),
            "unsurfaced_targets": [
                outcome.path for outcome in missed_anchored if outcome not in surfaced
            ],
        },
    )


def question_count(session: dict[str, Any], manifest: Manifest, run_report: dict | None) -> Dimension:
    questions = session.get("review_questions") or []
    hours = manifest.excerpt_duration_ms / 3_600_000
    cap = (run_report or {}).get("max_questions")
    return Dimension(
        name="question_count",
        criterion="question count",
        measured=True,
        basis=(
            f"{len(questions)} review questions on the session, over an annotated excerpt "
            f"of {manifest.excerpt_duration_ms / 1000:.1f} s"
        ),
        caveat=(
            "a count, not a quality. A run that asks nothing scores best here and may "
            "simply have missed everything, which is why this dimension is only readable "
            "beside surfaced_errors. The per-hour figure assumes the run covered the "
            "annotated excerpt and no more"
            + ("" if cap is not None else "; the queue cap in force was not recorded in any run report")
        ),
        value={
            "review_questions": len(questions),
            "questions_per_recorded_hour": round(len(questions) / hours, 2) if hours else None,
            "cap_in_force": cap,
        },
    )


def processing_time(manifest: Manifest, run_report: dict | None) -> Dimension:
    wall = (run_report or {}).get("wall_clock_s")
    if wall is None:
        return Dimension(
            name="processing_time",
            criterion="time",
            measured=False,
            basis="none",
            caveat="",
            missing=(
                "no run report carrying `wall_clock_s` was supplied. `rpg-chronicle "
                "run-audio --run-report <path>` writes one; pass it to this command with "
                "--run-report. Wall time cannot be recovered from a session directory "
                "afterwards, because nothing in the canonical session records when the "
                "run started"
            ),
        )
    hours = manifest.excerpt_duration_ms / 3_600_000
    return Dimension(
        name="processing_time",
        criterion="time",
        measured=True,
        basis=(
            f"wall_clock_s={wall} from the supplied run report, against an annotated "
            f"excerpt of {manifest.excerpt_duration_ms / 1000:.1f} s"
        ),
        caveat=(
            "wall time on one machine with whatever else was running on it, not a "
            "portable cost. It covers the pipeline the report was written for and "
            "excludes anything done before it -- acquisition, conversion to 16 kHz mono, "
            "and model loading outside the timed region. The realtime factor assumes the "
            "run processed the annotated excerpt and no more; scoring a whole-episode run "
            "against a ten-minute excerpt makes it meaningless"
        ),
        value={
            "wall_clock_s": wall,
            "recorded_hours": round(hours, 4),
            "realtime_factor": round((manifest.excerpt_duration_ms / 1000) / wall, 2) if wall else None,
        },
    )


def peak_memory(run_report: dict | None) -> Dimension:
    for key in ("peak_rss_bytes", "peak_memory_bytes", "max_rss_bytes"):
        value = (run_report or {}).get(key)
        if value is not None:
            return Dimension(
                name="peak_memory",
                criterion="memory",
                measured=True,
                basis=f"{key}={value} from the supplied run report",
                caveat=(
                    "peak resident set size for the process that wrote the report, which "
                    "excludes memory taken by any engine run as a separate process"
                ),
                value={"peak_rss_bytes": value, "peak_rss_mib": round(int(value) / 1048576, 1)},
            )
    return Dimension(
        name="peak_memory",
        criterion="memory",
        measured=False,
        basis="none",
        caveat="",
        missing=(
            "nothing in this repository records memory. The canonical session has no "
            "field for it, and the run report `run-audio --run-report` writes carries "
            "wall_clock_s and no memory figure. Closing this needs a peak-RSS reading "
            "taken inside the run -- `resource.getrusage(RUSAGE_SELF).ru_maxrss` plus "
            "RUSAGE_CHILDREN, since whisper.cpp is a subprocess and the parent's figure "
            "would miss the engine entirely -- added to that report. That report belongs "
            "to the run-audio command rather than to this harness, so this dimension is "
            "reported unmeasurable rather than closed by editing another goal's wiring"
        ),
    )


def review_burden(session: dict[str, Any], manifest: Manifest) -> Dimension:
    questions = len(session.get("review_questions") or [])
    scenes = len(session.get("scenes") or [])
    hours = manifest.excerpt_duration_ms / 3_600_000
    seconds = questions * ASSUMED_SECONDS_PER_QUESTION + scenes * ASSUMED_SECONDS_PER_SCENE
    per_hour = seconds / hours if hours else None
    return Dimension(
        name="review_burden",
        criterion="review burden",
        measured=True,
        basis=(
            f"proxy: {questions} questions x {ASSUMED_SECONDS_PER_QUESTION}s + {scenes} "
            f"scenes x {ASSUMED_SECONDS_PER_SCENE}s, over "
            f"{manifest.excerpt_duration_ms / 1000:.1f} s of recorded audio"
        ),
        caveat=(
            "a proxy, and the two constants in it are assumptions nobody has measured. No "
            "human has been timed reviewing a session produced by this pipeline, so this "
            "number cannot be compared against "
            f"{REVIEW_BURDEN_TARGET_SECONDS_PER_HOUR}s per recorded hour "
            "(`docs/PRODUCT.md`, personal alpha) as though it were the same quantity. It "
            "is a shape that moves the right way -- more questions and more scenes cost "
            "more attention -- and a number whose absolute value means nothing until one "
            "review is timed. It also assumes review is summary-first, since it prices no "
            "transcript reading at all"
        ),
        value={
            "estimated_seconds": seconds,
            "estimated_seconds_per_recorded_hour": round(per_hour, 1) if per_hour else None,
            "target_seconds_per_recorded_hour": REVIEW_BURDEN_TARGET_SECONDS_PER_HOUR,
            "within_target": (per_hour is not None and per_hour <= REVIEW_BURDEN_TARGET_SECONDS_PER_HOUR),
            "assumed_seconds_per_question": ASSUMED_SECONDS_PER_QUESTION,
            "assumed_seconds_per_scene": ASSUMED_SECONDS_PER_SCENE,
            "constants_are_measured": False,
        },
    )


#: Dimensions whose value depends on the answer key, and which a contaminated run may not
#: report as a score. Time, memory, question count and review burden do not read the truth
#: at all, so contamination has nothing to say about them and marking them would be noise.
TRUTH_DEPENDENT = frozenset(
    {"entity_capture", "plot_capture", "unsupported_claims", "surfaced_errors"}
)


def score(
    manifest: Manifest,
    session_dir: Path,
    session: dict[str, Any],
    run_report: dict | None = None,
) -> dict[str, Any]:
    """Produce the full report for one run against one manifest."""
    verdict = contamination.assess(session, session_dir, manifest.contaminating_providers)
    basis = time_basis(session, manifest)
    outcomes = _target_outcomes(manifest, session, basis)

    unsupported = unsupported_claims(manifest, session)
    dimensions = [
        entity_capture(manifest, session, basis, outcomes),
        plot_capture(manifest, session, basis),
        unsupported,
        surfaced_errors(session, basis, outcomes, unsupported),
        processing_time(manifest, run_report),
        peak_memory(run_report),
        question_count(session, manifest, run_report),
        review_burden(session, manifest),
    ]
    if not verdict.scoreable:
        dimensions = [
            Dimension(
                **{
                    **asdict(dimension),
                    "contaminated": dimension.name in TRUTH_DEPENDENT,
                    "withheld_because": (
                        f"{verdict.state}: {verdict.explanation}"
                        if dimension.name in TRUTH_DEPENDENT
                        else None
                    ),
                }
            )
            for dimension in dimensions
        ]

    reported = [dimension for dimension in dimensions if dimension.reportable]
    withheld = [dimension for dimension in dimensions if dimension.measured and dimension.contaminated]
    return {
        "harness_version": HARNESS_VERSION,
        "session_id": session.get("session_id"),
        "session_dir": str(session_dir),
        "manifest_id": manifest.id,
        "manifest_path": str(manifest.path),
        "verdict": "reported" if verdict.scoreable else "withheld",
        "contamination": {
            "state": verdict.state,
            "explanation": verdict.explanation,
            "declared_contaminating_providers": verdict.declared,
            "matched": verdict.matched,
            "session_engine_identity": verdict.identity.sources,
        },
        "truth_provenance": {
            "annotation_status": manifest.annotation_status,
            "targets_by_basis": manifest.basis_census(),
            "note": (
                "audio_observed means a person heard it; audio_machine_assisted means "
                "tooling found it; metadata_inferred was never in the audio at all. A "
                "recall number is only as strong as the row it was computed over"
            ),
        },
        "time_basis": {
            "hypothesis": basis.hypothesis,
            "offset_ms": basis.offset_ms,
            "anchors_inside_session": basis.anchors_inside,
            "anchors_total": basis.anchors_total,
            "session_turn_span_ms": list(basis.session_span) if basis.session_span else None,
        },
        "coverage": {
            "criteria_named_by_m2": 7,
            "dimensions_computed": len(dimensions),
            "reported": len(reported),
            "withheld_as_contaminated": len(withheld),
            "unmeasurable": [
                {"name": dimension.name, "missing": dimension.missing}
                for dimension in dimensions
                if not dimension.measured
            ],
        },
        "dimensions": [dimension.to_dict() for dimension in dimensions],
    }
