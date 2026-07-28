"""The correction loop, tested as behaviour rather than as declared truth.

Both correction fixtures declare an entity list with a name spelt two ways and one thing
named twice. No test below asserts any of that: what is asserted is what the *software*
does when a person answers, which is why every test here would fail if the code it names
were deleted. `docs/GOAL_RULES.md` R2 is the standing rule, and this file is the one most
exposed to breaking it -- a test reading "the fixture says Vesh Kalder, and after the
correction the session says Vesh Calder" is evidence; a test reading "the fixture declares
four questions" is not, and there is none.
"""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

from rpg_chronicle.analysis.prompts import ApprovedName, window_user_prompt
from rpg_chronicle.model import CanonicalSession, Entity, Evidence, TranscriptTurn
from rpg_chronicle.pipeline import build_review_package, load_session, run_pipeline
from rpg_chronicle.providers import FixtureAnalysisProvider, FixtureTranscriptProvider
from rpg_chronicle.review.answers import AnswerError, parse_answer_sheet
from rpg_chronicle.review.apply import apply_answers, carry_forward
from rpg_chronicle.review.console import Console, ReviewAborted, collect_answers
from rpg_chronicle.review.record import RECORD_FILENAME, CorrectionRecord
from rpg_chronicle.review.session import answer_session
from rpg_chronicle.review.vocabulary import STORE_FILENAME, Vocabulary

FIXTURES = Path(__file__).parents[1] / "benchmarks" / "fixtures"
FIRST = FIXTURES / "r0_correction_session_1.json"
SECOND = FIXTURES / "r0_correction_session_2.json"
PRE_GOAL_SESSION = FIXTURES / "sessions" / "pre-correction-loop"

NOW = "2026-07-28T09:00:00+00:00"
LATER = "2026-07-29T09:00:00+00:00"


def _run(fixture: Path, output: Path, vocabulary: Vocabulary | None = None):
    session_id = json.loads(fixture.read_text())["session"]["id"]
    return run_pipeline(
        fixture,
        output,
        FixtureTranscriptProvider(),
        FixtureAnalysisProvider(fixture),
        session_id=session_id,
        vocabulary=vocabulary,
        now=NOW,
    )


def _sheet(*answers, by: str = "karl"):
    return parse_answer_sheet({"answered_by": by, "answers": list(answers)}, default_answered_by=by)


def _named(session: CanonicalSession, name: str) -> Entity:
    matches = [entity for entity in session.entities if entity.name == name]
    assert len(matches) == 1, f"expected exactly one entity named {name!r}, got {matches}"
    return matches[0]


MERGE_THE_WARDEN = {
    "question_id": "question-001",
    "action": "accept",
    "operation": {"op": "merge_entities", "entity_id": "entity-002", "absorbs": ["entity-003"]},
}
SPELL_THE_CHANDLER = {
    "question_id": "question-002",
    "action": "correct",
    "operation": {"op": "revise_entity", "entity_id": "entity-001", "name": "Vesh Calder"},
}


@pytest.fixture
def answered(tmp_path):
    """A first session, run and then answered. The starting point for most of this file."""
    output = tmp_path / "campaign"
    _run(FIRST, output)
    session_dir = output / "r0-correction-hollow-bell-1"
    reviewed = answer_session(
        session_dir,
        _sheet(
            MERGE_THE_WARDEN,
            SPELL_THE_CHANDLER,
            {"question_id": "question-003", "action": "defer"},
            {"question_id": "question-004", "action": "irrelevant"},
        ),
        now=NOW,
    )
    return output, session_dir, reviewed


# -- an answer changes the session ------------------------------------------------------


def test_an_answer_changes_the_canonical_session_on_disk(answered):
    _, session_dir, _ = answered
    stored = load_session(session_dir / "canonical-session.json")

    chandler = _named(stored, "Vesh Calder")
    assert "Vesh Kalder" in chandler.aliases

    warden = _named(stored, "the Tallow Warden")
    assert "Ormunt" in warden.aliases
    assert not [entity for entity in stored.entities if entity.name == "Ormunt"]


def test_a_merge_widens_the_evidence_to_cover_both_records(answered):
    _, session_dir, _ = answered
    stored = load_session(session_dir / "canonical-session.json")
    warden = _named(stored, "the Tallow Warden")
    turns_by_id = {turn.id: turn for turn in stored.turns}

    cited = [turns_by_id[turn_id] for turn_id in warden.evidence.turn_ids]
    assert len(cited) > 1, "a merged entity must carry the evidence of everything folded in"
    assert warden.evidence.start_ms == min(turn.start_ms for turn in cited)
    assert warden.evidence.end_ms == max(turn.end_ms for turn in cited)


def test_every_answered_question_carries_its_disposition(answered):
    _, session_dir, _ = answered
    stored = load_session(session_dir / "canonical-session.json")
    assert {question.id: question.status for question in stored.review_questions} == {
        "question-001": "accepted",
        "question-002": "corrected",
        "question-003": "deferred",
        "question-004": "irrelevant",
    }


def test_the_engines_original_value_stays_recoverable(answered):
    _, session_dir, _ = answered
    record = CorrectionRecord.load(
        session_dir / RECORD_FILENAME, session_id="r0-correction-hollow-bell-1"
    )
    original = record.original("entity-001")
    assert original is not None
    assert original["entities"][0]["name"] == "Vesh Kalder"

    folded = record.original("entity-002")
    assert folded is not None
    assert [item["name"] for item in folded["entities"]] == ["the Tallow Warden", "Ormunt"]


def test_the_record_says_who_answered_and_when(answered):
    _, session_dir, _ = answered
    record = CorrectionRecord.load(
        session_dir / RECORD_FILENAME, session_id="r0-correction-hollow-bell-1"
    )
    assert [entry.action for entry in record.entries] == [
        "accept",
        "correct",
        "defer",
        "irrelevant",
    ]
    assert {entry.answered_by for entry in record.entries} == {"karl"}
    assert {entry.answered_at for entry in record.entries} == {NOW}


def test_correcting_a_name_never_rewrites_the_transcript(answered):
    """The one thing this loop refuses to be.

    A correction changes the campaign record. `docs/PRODUCT.md` says preserve original
    inputs, and a turn is what the recognizer heard. If this ever goes red, the loop has
    become a transcript editor.
    """
    _, session_dir, _ = answered
    stored = load_session(session_dir / "canonical-session.json")
    text = " ".join(turn.text for turn in stored.turns)
    assert "Vesh Kalder" in text
    assert "Ormunt" in text


def test_a_deferred_question_leaves_the_entities_alone(tmp_path):
    output = tmp_path / "campaign"
    before = _run(FIRST, output)
    names_before = [(entity.id, entity.name) for entity in before.entities]

    session_dir = output / "r0-correction-hollow-bell-1"
    answer_session(session_dir, _sheet({"question_id": "question-003", "action": "defer"}), now=NOW)

    after = load_session(session_dir / "canonical-session.json")
    assert [(entity.id, entity.name) for entity in after.entities] == names_before


def test_the_rewritten_review_package_shows_the_corrected_session(answered):
    _, session_dir, _ = answered
    package = json.loads((session_dir / "review-package.json").read_text())
    names = {entity["name"] for entity in package["entities"]}
    assert "Vesh Calder" in names
    assert "Vesh Kalder" not in names
    assert {item["id"]: item["status"] for item in package["needs_attention"]}[
        "question-002"
    ] == "corrected"


# -- refusals ---------------------------------------------------------------------------


def test_an_answer_to_a_question_the_session_lacks_is_refused(tmp_path):
    output = tmp_path / "campaign"
    _run(FIRST, output)
    with pytest.raises(AnswerError, match="question-999"):
        answer_session(
            output / "r0-correction-hollow-bell-1",
            _sheet({"question_id": "question-999", "action": "accept"}),
            now=NOW,
        )


def test_an_operation_on_an_entity_the_session_lacks_is_refused(tmp_path):
    output = tmp_path / "campaign"
    _run(FIRST, output)
    with pytest.raises(AnswerError, match="entity-404"):
        answer_session(
            output / "r0-correction-hollow-bell-1",
            _sheet(
                {
                    "question_id": "question-002",
                    "action": "correct",
                    "operation": {"op": "revise_entity", "entity_id": "entity-404", "name": "X"},
                }
            ),
            now=NOW,
        )


def test_two_answers_reaching_for_the_same_entity_are_refused(tmp_path):
    output = tmp_path / "campaign"
    _run(FIRST, output)
    with pytest.raises(AnswerError, match="both change entity"):
        answer_session(
            output / "r0-correction-hollow-bell-1",
            _sheet(
                SPELL_THE_CHANDLER,
                {
                    "question_id": "question-003",
                    "action": "correct",
                    "operation": {
                        "op": "revise_entity",
                        "entity_id": "entity-001",
                        "name": "Vesh Kaldar",
                    },
                },
            ),
            now=NOW,
        )


def test_a_refused_sheet_writes_nothing_at_all(tmp_path):
    """Whole or nothing. A half-applied batch leaves the person guessing what landed."""
    output = tmp_path / "campaign"
    _run(FIRST, output)
    session_dir = output / "r0-correction-hollow-bell-1"
    before = (session_dir / "canonical-session.json").read_text()

    with pytest.raises(AnswerError):
        answer_session(
            session_dir,
            _sheet(
                SPELL_THE_CHANDLER,
                {"question_id": "question-404", "action": "defer"},
            ),
            now=NOW,
        )

    assert (session_dir / "canonical-session.json").read_text() == before
    assert not (session_dir / RECORD_FILENAME).exists()
    assert not (output / STORE_FILENAME).exists()


def test_an_action_that_changes_nothing_cannot_carry_an_operation():
    with pytest.raises(AnswerError, match="cannot carry an operation"):
        _sheet(
            {
                "question_id": "question-001",
                "action": "defer",
                "operation": {"op": "revise_entity", "entity_id": "entity-001", "name": "X"},
            }
        )


def test_answering_one_question_twice_in_a_sheet_is_refused():
    with pytest.raises(AnswerError, match="more than once"):
        _sheet(
            {"question_id": "question-003", "action": "defer"},
            {"question_id": "question-003", "action": "irrelevant"},
        )


def test_merging_across_kinds_needs_the_surviving_kind_stated(tmp_path):
    """D-018 keeps both records when two windows disagree about a kind. Resolving that
    by whichever entity the model emitted first would be an accident, not an answer."""
    turns = [
        TranscriptTurn(id="turn-001", start_ms=0, end_ms=1000, text="The Weir speaks."),
        TranscriptTurn(id="turn-002", start_ms=1000, end_ms=2000, text="The Weir marches."),
    ]
    turns_by_id = {turn.id: turn for turn in turns}
    entities = [
        Entity("entity-001", "the Weir", "character", [], Evidence(["turn-001"], 0, 1000)),
        Entity("entity-002", "the Weir", "faction", [], Evidence(["turn-002"], 1000, 2000)),
    ]
    session = CanonicalSession(
        schema_version="0.2",
        session_id="kinds",
        source={},
        status="analyzed",
        turns=turns,
        entities=entities,
        review_questions=[],
    )
    from rpg_chronicle.review.answers import MergeEntities
    from rpg_chronicle.review.apply import _apply_operation

    with pytest.raises(AnswerError, match="entity_kind"):
        _apply_operation(
            entities,
            MergeEntities(entity_id="entity-001", absorbs=("entity-002",)),
            turns_by_id,
            where="test",
        )
    assert len(session.entities) == 2


# -- a correction never discards what somebody authored ---------------------------------


def test_a_second_person_cannot_quietly_replace_the_first_persons_decision(answered):
    _, session_dir, _ = answered
    with pytest.raises(AnswerError, match="already settled by 'karl'"):
        answer_session(
            session_dir,
            _sheet(
                {
                    "question_id": "question-002",
                    "action": "correct",
                    "operation": {
                        "op": "revise_entity",
                        "entity_id": "entity-001",
                        "name": "Vesh Khaldur",
                    },
                },
                by="a-different-player",
            ),
            now=LATER,
        )

    stored = load_session(session_dir / "canonical-session.json")
    assert _named(stored, "Vesh Calder")


def test_overriding_records_the_disagreement_and_keeps_the_earlier_value(answered):
    _, session_dir, _ = answered
    answer_session(
        session_dir,
        _sheet(
            {
                "question_id": "question-002",
                "action": "correct",
                "operation": {
                    "op": "revise_entity",
                    "entity_id": "entity-001",
                    "name": "Vesh Khaldur",
                },
                "note": "The shop sign is a different man's.",
            },
            by="a-different-player",
        ),
        now=LATER,
        override=True,
    )

    stored = load_session(session_dir / "canonical-session.json")
    assert _named(stored, "Vesh Khaldur")

    record = CorrectionRecord.load(
        session_dir / RECORD_FILENAME, session_id="r0-correction-hollow-bell-1"
    )
    # The first person's decision is still in the file, and still attributed to them.
    assert record.original("entity-001")["entities"][0]["name"] == "Vesh Kalder"
    superseded = [entry for entry in record.entries if entry.answered_by == "karl"]
    assert any(
        change.after["entities"][0]["name"] == "Vesh Calder"
        for entry in superseded
        for change in entry.changes
    )


def test_a_disagreement_between_two_people_makes_the_name_contested(answered):
    output, session_dir, _ = answered
    answer_session(
        session_dir,
        _sheet(
            {
                "question_id": "question-002",
                "action": "correct",
                "operation": {
                    "op": "revise_entity",
                    "entity_id": "entity-001",
                    "name": "Vesh Khaldur",
                },
            },
            by="a-different-player",
        ),
        now=LATER,
        override=True,
    )
    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    entry = vocabulary.resolve("character", "Vesh Kalder")
    assert entry is not None
    assert entry.contested
    assert len(entry.approvals) == 2


def test_one_person_changing_their_own_mind_is_not_a_disagreement(answered):
    output, session_dir, _ = answered
    answer_session(
        session_dir,
        _sheet(
            {
                "question_id": "question-002",
                "action": "correct",
                "operation": {
                    "op": "revise_entity",
                    "entity_id": "entity-001",
                    "name": "Vesh Kaldyr",
                },
            },
            by="karl",
        ),
        now=LATER,
    )
    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    entry = vocabulary.resolve("character", "Vesh Kaldyr")
    assert entry is not None
    assert not entry.contested
    assert entry.canonical == "Vesh Kaldyr"


# -- the answer reaches the next run ----------------------------------------------------


def test_a_later_session_is_analysed_differently_because_of_the_earlier_answer(answered):
    """Acceptance item 2, stated as a difference rather than as a property.

    The control run and the carried run consume the identical fixture through the
    identical provider. Everything about them is the same except that one was given the
    vocabulary the first session's answers produced. Deleting the `carry_forward` call in
    `pipeline.run_pipeline` turns this red and nothing else in the suite.
    """
    output, _, _ = answered
    vocabulary = Vocabulary.load(output / STORE_FILENAME)

    control = _run(SECOND, output.parent / "control")
    carried = _run(SECOND, output, vocabulary=vocabulary)

    assert {entity.name for entity in control.entities} >= {"Ormunt", "Vesh Kalder"}
    assert {entity.name for entity in carried.entities} >= {"the Tallow Warden", "Vesh Calder"}
    assert "Ormunt" not in {entity.name for entity in carried.entities}


def test_a_carried_name_keeps_the_spelling_this_session_actually_used(answered):
    output, _, _ = answered
    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    carried = _run(SECOND, output, vocabulary=vocabulary)
    warden = _named(carried, "the Tallow Warden")
    assert "Ormunt" in warden.aliases


def test_a_carried_name_is_recorded_in_the_later_sessions_own_record(answered):
    output, _, _ = answered
    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    carried = _run(SECOND, output, vocabulary=vocabulary)

    record = CorrectionRecord.load(
        output / carried.session_id / RECORD_FILENAME, session_id=carried.session_id
    )
    assert record.entries, "a change nothing recorded is the silent edit rule 12 forbids"
    assert {entry.action for entry in record.entries} == {"carry_forward"}
    assert {entry.answered_by for entry in record.entries} == {"vocabulary"}
    assert record.original("entity-001")["entities"][0]["name"] == "Ormunt"
    assert carried.provenance["corrections"]["entries"] == len(record.entries)


def test_carrying_forward_does_not_import_a_spelling_this_session_never_used(answered):
    """An alias is part of a claim carrying evidence. Attaching a spelling to turns that
    never contained it would manufacture support for it."""
    output, _, _ = answered
    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    carried = _run(SECOND, output, vocabulary=vocabulary)

    chandler = _named(carried, "Vesh Calder")
    assert chandler.aliases == ["Vesh Kalder"]
    turns = " ".join(turn.text for turn in carried.turns)
    for alias in chandler.aliases:
        assert alias in turns


def test_a_contested_name_is_left_alone_and_the_refusal_is_written_down(answered):
    output, session_dir, _ = answered
    answer_session(
        session_dir,
        _sheet(
            {
                "question_id": "question-002",
                "action": "correct",
                "operation": {
                    "op": "revise_entity",
                    "entity_id": "entity-001",
                    "name": "Vesh Khaldur",
                },
            },
            by="a-different-player",
        ),
        now=LATER,
        override=True,
    )

    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    carried = _run(SECOND, output, vocabulary=vocabulary)

    assert _named(carried, "Vesh Kalder"), "a contested spelling must not be applied"
    record = CorrectionRecord.load(
        output / carried.session_id / RECORD_FILENAME, session_id=carried.session_id
    )
    declined = [entry for entry in record.entries if entry.declined]
    assert declined and "approved, by different people" in declined[0].declined


def test_a_surface_form_is_matched_whole_and_never_as_a_substring():
    """The over-application risk, tested directly. One approved spelling loose in a
    matcher rewrites places nobody looked at."""
    vocabulary = Vocabulary()
    vocabulary.approve(
        kind="character",
        canonical="the Tallow Warden",
        aliases=["Ormunt"],
        approved_by="karl",
        approved_at=NOW,
        session_id="one",
    )
    assert vocabulary.resolve("character", "Ormunt") is not None
    assert vocabulary.resolve("character", "Ormunt's brother") is None
    assert vocabulary.resolve("character", "Orm") is None
    assert vocabulary.resolve("place", "Ormunt") is None, "kind is part of the identity"


def test_carry_forward_leaves_a_session_it_has_nothing_to_say_about_untouched(tmp_path):
    vocabulary = Vocabulary()
    vocabulary.approve(
        kind="character",
        canonical="Somebody Else",
        aliases=["Someone Else"],
        approved_by="karl",
        approved_at=NOW,
        session_id="elsewhere",
    )
    output = tmp_path / "campaign"
    session = _run(SECOND, output, vocabulary=vocabulary)
    assert {entity.name for entity in session.entities} >= {"Ormunt", "Vesh Kalder"}
    assert not (output / session.session_id / RECORD_FILENAME).exists()


def test_carry_forward_is_a_no_op_when_the_name_is_already_canonical(answered):
    output, _, _ = answered
    vocabulary = Vocabulary.load(output / STORE_FILENAME)
    session = load_session(output / "r0-correction-hollow-bell-1" / "canonical-session.json")
    record = CorrectionRecord.load(tmp_record := (output / "unused.json"), session_id=session.session_id)

    outcome = carry_forward(session, vocabulary, record=record, now=LATER)

    assert outcome.changed_entities == ()
    assert record.entries == []
    assert not tmp_record.exists()


# -- a session written before this goal -------------------------------------------------


def test_a_session_written_before_this_goal_loads_resumes_and_can_be_answered(tmp_path):
    """Acceptance item 4. The payload is a session this repository wrote on `main`
    before `src/rpg_chronicle/review/` existed -- see the README beside it."""
    output = tmp_path / "campaign"
    session_dir = output / "r0-synthetic-crossroads"
    session_dir.mkdir(parents=True)
    for name in ("canonical-session.json", "review-package.json"):
        shutil.copy(PRE_GOAL_SESSION / name, session_dir / name)

    fixture = FIXTURES / "r0_synthetic_session.json"
    resumed = run_pipeline(
        fixture,
        output,
        FixtureTranscriptProvider(),
        FixtureAnalysisProvider(fixture),
        session_id="r0-synthetic-crossroads",
    )
    assert resumed.status == "review_ready"

    stored = json.loads((PRE_GOAL_SESSION / "review-package.json").read_text())
    assert "id" not in stored["needs_attention"][0], (
        "the payload must predate this goal, or it demonstrates nothing"
    )

    reviewed = answer_session(
        session_dir,
        _sheet({"question_id": "question-001", "action": "accept"}),
        now=NOW,
    )
    assert reviewed.outcome.dispositions == {"question-001": "accepted"}
    assert load_session(session_dir / "canonical-session.json").review_questions[0].status == (
        "accepted"
    )


def test_the_review_package_now_names_the_questions_it_asks(tmp_path):
    session = _run(FIRST, tmp_path / "campaign")
    package = build_review_package(session)
    for item in package["needs_attention"]:
        assert item["id"], "an answer has to be able to name what it is answering"
        assert item["status"] == "open"
        assert item["actions"] == ["accept", "correct", "defer", "irrelevant"]


# -- the surface a person actually uses -------------------------------------------------


def test_the_queue_shows_evidence_and_the_things_that_evidence_names(tmp_path):
    session = _run(FIRST, tmp_path / "campaign")
    stdout = io.StringIO()
    console = Console(stdin=io.StringIO("d\n\n" * 20), stdout=stdout)

    collect_answers(session, console=console, answered_by="karl")
    shown = stdout.getvalue()

    assert "the Tallow Warden" in shown and "Ormunt" in shown
    assert "[turn-006]" in shown, "a question must arrive with the turns it cites"
    assert "Why it matters" in shown
    # The bounded surface: cited turns only, never the whole transcript.
    assert "the good lantern" not in shown.split("[4/4]")[0]


def test_the_queue_only_offers_questions_that_are_still_open(answered):
    _, session_dir, _ = answered
    session = load_session(session_dir / "canonical-session.json")
    stdout = io.StringIO()
    collect_answers(
        session,
        console=Console(stdin=io.StringIO(""), stdout=stdout),
        answered_by="karl",
    )
    assert "0 question(s)" in stdout.getvalue()


def test_quitting_the_queue_returns_no_answers_at_all(tmp_path):
    session = _run(FIRST, tmp_path / "campaign")
    with pytest.raises(ReviewAborted):
        collect_answers(
            session,
            console=Console(stdin=io.StringIO("a\n\n\nq\n"), stdout=io.StringIO()),
            answered_by="karl",
        )


def test_an_interactive_rename_produces_the_same_answer_a_sheet_would(tmp_path):
    """The two surfaces must not drift. One of them is what a person uses and the other
    is what the acceptance evidence exercises."""
    session = _run(FIRST, tmp_path / "campaign")
    # question-001, accept, rename the first listed entity, no note; then skip the rest.
    script = "a\nr\n1\nthe Tallow Warden of Wrackford\n\n" + "s\n" * 5
    sheet = collect_answers(
        session,
        console=Console(stdin=io.StringIO(script), stdout=io.StringIO()),
        answered_by="karl",
    )
    assert len(sheet.answers) == 1
    answer = sheet.answers[0]
    assert answer.question_id == "question-001"
    assert answer.action == "accept"
    assert answer.operation.name == "the Tallow Warden of Wrackford"


# -- what a settled name tells the next analysis ----------------------------------------


def test_settled_names_reach_the_prompt_the_model_is_given():
    turns = [TranscriptTurn(id="turn-001", start_ms=0, end_ms=1000, text="Anything at all.")]
    prompt = window_user_prompt(
        turns,
        index=0,
        total=1,
        approved_names=(ApprovedName("Vesh Calder", "character", ("Vesh Kalder",)),),
    )
    assert "Vesh Calder" in prompt
    assert "Vesh Kalder" in prompt
    assert "not a claim that any of them appear here" in prompt


def test_a_prompt_with_no_settled_names_gains_nothing():
    turns = [TranscriptTurn(id="turn-001", start_ms=0, end_ms=1000, text="Anything at all.")]
    assert window_user_prompt(turns, index=0, total=1) == window_user_prompt(
        turns, index=0, total=1, approved_names=()
    )


def test_a_contested_name_is_never_put_in_a_prompt(answered):
    from rpg_chronicle.cli import approved_names

    output, session_dir, _ = answered
    answer_session(
        session_dir,
        _sheet(
            {
                "question_id": "question-002",
                "action": "correct",
                "operation": {
                    "op": "revise_entity",
                    "entity_id": "entity-001",
                    "name": "Vesh Khaldur",
                },
            },
            by="a-different-player",
        ),
        now=LATER,
        override=True,
    )
    names = approved_names(Vocabulary.load(output / STORE_FILENAME))
    assert "the Tallow Warden" in {name.canonical for name in names}
    assert not [name for name in names if "Vesh" in name.canonical]


# -- the record itself ------------------------------------------------------------------


def test_a_record_refuses_to_be_appended_to_from_another_session(answered):
    _, session_dir, _ = answered
    with pytest.raises(ValueError, match="belongs to one session"):
        CorrectionRecord.load(session_dir / RECORD_FILENAME, session_id="some-other-session")


def test_apply_answers_reports_what_it_did(tmp_path):
    output = tmp_path / "campaign"
    session = _run(FIRST, output)
    record = CorrectionRecord.load(output / "nowhere.json", session_id=session.session_id)
    vocabulary = Vocabulary()

    outcome = apply_answers(
        session,
        _sheet(MERGE_THE_WARDEN, {"question_id": "question-003", "action": "defer"}),
        record=record,
        vocabulary=vocabulary,
        now=NOW,
    )
    assert outcome.applied == ("question-001", "question-003")
    assert outcome.changed_entities == ("entity-002",)
    assert outcome.vocabulary_entries == ("the Tallow Warden",)
    assert outcome.dispositions["question-003"] == "deferred"


# -- the command a person actually types ------------------------------------------------


def _cli(*argv):
    from rpg_chronicle import cli

    parser = cli._parser()
    args = parser.parse_args(argv)
    handlers = {"run-fixture": cli._run_fixture, "review": cli._review}
    handlers[args.command](args)


def test_the_review_command_applies_a_sheet_and_says_what_it_did(tmp_path, capsys):
    output = tmp_path / "campaign"
    _cli("run-fixture", str(FIRST), "--output", str(output))
    sheet = tmp_path / "answers.json"
    sheet.write_text(json.dumps({"answered_by": "karl", "answers": [SPELL_THE_CHANDLER]}))

    _cli("review", str(output / "r0-correction-hollow-bell-1"), "--answers", str(sheet))

    printed = capsys.readouterr().out
    assert "1 answered" in printed
    assert "'Vesh Kalder' -> 'Vesh Calder'" in printed
    stored = load_session(output / "r0-correction-hollow-bell-1" / "canonical-session.json")
    assert _named(stored, "Vesh Calder")


def test_a_dry_run_reports_the_change_and_writes_nothing(tmp_path, capsys):
    output = tmp_path / "campaign"
    _cli("run-fixture", str(FIRST), "--output", str(output))
    session_dir = output / "r0-correction-hollow-bell-1"
    before = (session_dir / "canonical-session.json").read_text()
    sheet = tmp_path / "answers.json"
    sheet.write_text(json.dumps({"answered_by": "karl", "answers": [SPELL_THE_CHANDLER]}))

    _cli("review", str(session_dir), "--answers", str(sheet), "--dry-run")

    assert "nothing was written" in capsys.readouterr().out
    assert (session_dir / "canonical-session.json").read_text() == before
    assert not (session_dir / RECORD_FILENAME).exists()
    assert not (output / STORE_FILENAME).exists()


def test_a_refused_sheet_is_a_usage_error_rather_than_a_traceback(tmp_path, monkeypatch):
    """Through `main`, not around it. Re-implementing the handler here would test a copy
    of the error handling rather than the one a person hits."""
    from rpg_chronicle import cli

    output = tmp_path / "campaign"
    _cli("run-fixture", str(FIRST), "--output", str(output))
    sheet = tmp_path / "answers.json"
    sheet.write_text(
        json.dumps({"answered_by": "karl", "answers": [{"question_id": "nope", "action": "defer"}]})
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "rpg-chronicle",
            "review",
            str(output / "r0-correction-hollow-bell-1"),
            "--answers",
            str(sheet),
        ],
    )
    with pytest.raises(SystemExit, match="answers refused"):
        cli.main()


def test_a_run_with_no_carry_forward_reproduces_the_analysis_alone(tmp_path, capsys):
    output = tmp_path / "campaign"
    _cli("run-fixture", str(FIRST), "--output", str(output))
    sheet = tmp_path / "answers.json"
    sheet.write_text(json.dumps({"answered_by": "karl", "answers": [SPELL_THE_CHANDLER]}))
    _cli("review", str(output / "r0-correction-hollow-bell-1"), "--answers", str(sheet))
    capsys.readouterr()

    _cli("run-fixture", str(SECOND), "--output", str(output), "--no-carry-forward")

    assert "carried forward" not in capsys.readouterr().out
    later = load_session(output / "r0-correction-hollow-bell-2" / "canonical-session.json")
    assert _named(later, "Vesh Kalder")


def test_a_contested_name_can_be_settled_by_agreeing(tmp_path):
    """Contested is a state with an exit, or the store's own promise is false.

    It says a disputed name is left alone "until a person settles it". If the flag
    latched, settling it would be impossible and carrying that name forward would be
    dead for the life of the campaign.
    """
    vocabulary = Vocabulary()
    common = {"kind": "character", "aliases": ["Vesh Kalder"], "session_id": "one"}
    vocabulary.approve(canonical="Vesh Calder", approved_by="karl", approved_at=NOW, **common)
    entry = vocabulary.approve(
        canonical="Vesh Khaldur", approved_by="another-player", approved_at=LATER, **common
    )
    assert entry.contested

    settled = vocabulary.approve(
        canonical="Vesh Khaldur", approved_by="karl", approved_at="2026-07-30T09:00:00+00:00",
        **common,
    )
    assert not settled.contested
    assert settled.canonical == "Vesh Khaldur"
    assert len(settled.approvals) == 3, "agreeing must not discard the history of the dispute"


def test_a_third_person_can_reopen_a_settled_name(tmp_path):
    vocabulary = Vocabulary()
    common = {"kind": "character", "aliases": ["Vesh Kalder"], "session_id": "one"}
    vocabulary.approve(canonical="Vesh Calder", approved_by="karl", approved_at=NOW, **common)
    entry = vocabulary.approve(
        canonical="Vesh Kaldyr", approved_by="a-third-player", approved_at=LATER, **common
    )
    assert entry.contested
