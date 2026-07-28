"""What the name-uncertainty signal must do, with the lexicon supplied by the test.

The lexicon is injected rather than imported, so nothing here depends on `wordfreq` being
installed or on whatever wordlist the machine running CI happens to ship. Two tests do use
real engine output: `research/probes/results/synthetic-whisper-cpp-metal.json` is
whisper.cpp's transcript of the rights-clear synthetic clip, committed by R01. That is
recognized text and not declared truth, which is the difference between measuring the
signal and asserting a fixture back at itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from rpg_chronicle.transcription.name_uncertainty import (
    find_uncertain_names,
    is_rare,
    neighbours,
)

RESULTS = Path(__file__).resolve().parents[1] / "research/probes/results"


@dataclass
class Turn:
    """Only `id` and `text`.

    Deliberately without a `confidence` attribute: this goal's central constraint is that
    the signal is not a confidence threshold, and a turn that cannot answer the question
    makes reading it an AttributeError rather than a judgement call.
    """

    id: str
    text: str


class StubLexicon:
    """Zipf frequencies for the handful of words a test names, 0.0 for everything else.

    A mapping rather than keyword arguments, because several of the words that matter
    here -- `and`, `is`, `it` -- are Python keywords.
    """

    def __init__(self, frequencies: dict[str, float]) -> None:
        self._frequencies = {word.lower(): value for word, value in frequencies.items()}

    def zipf(self, word: str) -> float:
        return self._frequencies.get(word.lower(), 0.0)


ORDINARY = StubLexicon(
    {
        "the": 7.0, "road": 5.0, "out": 6.0, "of": 7.0, "narrows": 4.0, "toward": 5.0,
        "checks": 5.0, "modifier": 3.5, "bran": 3.3, "warden": 4.2,
        "see": 6.0, "anything": 5.5, "moving": 5.0, "on": 6.5, "ridge": 4.2,
        "want": 6.0, "perception": 4.5, "check": 5.5, "does": 6.0, "cat": 5.5,
        "nag": 3.6, "and": 7.0, "again": 5.5, "her": 6.0, "up": 6.0, "is": 7.0,
        "it": 7.0, "a": 7.0, "plan": 5.0, "bad": 6.0, "already": 6.0, "inside": 5.5,
        "apply": 5.0, "moved": 5.5, "waits": 4.5, "idea": 5.5, "late": 5.5,
    }
)


def test_a_name_spelled_two_ways_becomes_one_candidate() -> None:
    """The engine contradicting itself is the signal's whole point.

    `Gartog's` and `Garthog` are what whisper.cpp actually produced for one character in
    ten minutes of the benchmark recording. If they arrive as two candidates, the person
    is asked two questions about one name and neither carries the other's evidence.
    """
    turns = [
        Turn("t0", "Gartog's plan is bad."),
        Turn("t1", "Garthog is already inside."),
    ]
    candidates = find_uncertain_names(turns, lexicon=ORDINARY, floor=2.0)
    assert len(candidates) == 1
    assert set(candidates[0].spellings) == {"Gartog's", "Garthog"}
    assert candidates[0].occurrences == 2
    assert "2 ways" in candidates[0].grounds


def test_ordinary_speech_produces_no_candidates() -> None:
    """A signal that flags everything is a review queue nobody opens."""
    turns = [
        Turn("t0", "The road out of the ridge narrows."),
        Turn("t1", "Does it see anything moving on the ridge?"),
    ]
    assert find_uncertain_names(turns, lexicon=ORDINARY, floor=2.0) == []


def test_a_plural_of_a_common_word_is_not_a_candidate() -> None:
    """`modifiers` is a common word wearing an `s`; `vegetators` is not.

    Only asking about the singular separates them, and without that check every regular
    plural the lexicon happens to omit arrives as a name.

    The stub deliberately gives `modifiers` no entry at all, so it is *below* the floor
    and the rarity check passes it through to the plural branch. An earlier version
    declared it at 3.5, which meant the rarity check filtered it first and this test named
    a branch it never reached -- it kept passing with the branch deleted, which is what
    the tautology rule exists to catch.

    **Tautology check.** Replacing the plural branch in `is_rare` with `return True` makes
    this fail: `modifiers` joins `vegetators` in the candidate list.
    """
    turns = [Turn("t0", "Apply the modifiers."), Turn("t1", "The vegetators moved.")]
    candidates = find_uncertain_names(turns, lexicon=ORDINARY, floor=2.0)
    assert [c.spellings for c in candidates] == [("vegetators",)]


def test_short_names_do_not_cluster_with_unrelated_short_words() -> None:
    """Two edits on a three-letter string reaches almost every three-letter string.

    Measured, not imagined: at a flat distance of two the probe called `nag` a spelling of
    `Kat`, `goes` a spelling of `Grey` and `eater` a spelling of `Reaper`. The tolerance
    has to grow with the length of the evidence the string carries.
    """
    assert neighbours("gartog", "garthog")
    assert neighbours("ente", "entei")
    assert not neighbours("kat", "nag")
    assert not neighbours("grey", "goes")
    assert not neighbours("reaper", "eater")


def test_the_possessive_reaches_the_bare_name() -> None:
    """`Gartog's` has to stem to `gartog` or the one real self-contradiction splits in two.

    The obvious `rstrip("'s")` is wrong and was wrong here first: it strips any trailing
    `'` or `s`, so `James` becomes `Jame` and every name ending in s is a near-miss of
    itself.
    """
    turns = [Turn("t0", "James's idea"), Turn("t1", "James is late")]
    candidates = find_uncertain_names(turns, lexicon=StubLexicon({"idea": 5.0, "late": 5.0, "is": 7.0}), floor=2.0)
    assert len(candidates) == 1
    assert set(candidates[0].spellings) == {"James's", "James"}


def test_the_signal_never_reads_confidence() -> None:
    """The goal's central constraint, enforced structurally rather than by inspection.

    `Turn` here has no `confidence` attribute at all, so a future edit that reaches for
    one raises instead of quietly reintroducing the threshold R01 measured as useless for
    entity errors.
    """
    turns = [Turn("t0", "Garthog waits.")]
    assert [c.spellings for c in find_uncertain_names(turns, lexicon=ORDINARY, floor=2.0)] == [
        ("Garthog",)
    ]


def test_rarity_is_decided_by_the_injected_lexicon() -> None:
    generous = StubLexicon({"garthog": 5.0})
    assert not is_rare("Garthog", generous, floor=2.0)
    assert is_rare("Garthog", ORDINARY, floor=2.0)


def test_it_selects_the_planted_mangles_in_real_engine_output() -> None:
    """Acceptance item 1, over whisper.cpp's own transcript of the synthetic clip.

    R01 planted four coined names and published what the engine wrote instead. Three of
    those substitutions are selected here; `Brann` -> `Bran` is not, because `Bran` is an
    ordinary English word and a signal built on rarity cannot see it. That miss is
    asserted rather than tolerated, so a later change that appears to fix it has to
    explain itself.

    **Tautology check.** This test fails when the rarity test in `is_rare` is deleted:
    with everything rare, `Bran` joins the candidates and the asserted miss becomes a hit.
    It also fails when `_stem`'s clitic handling is removed. It asserts over recognized
    text committed by R01, not over a declared `expected_analysis` block, so nothing here
    is a fixture agreeing with itself.
    """
    payload = json.loads((RESULTS / "synthetic-whisper-cpp-metal.json").read_text())
    turns = [Turn(t["id"], t["text"]) for t in payload["canonical_turns"]]

    class Wordfreq:
        """Frequencies for exactly the words this assertion turns on."""

        def zipf(self, word: str) -> float:
            table = {"bran": 3.30, "ashen": 3.55, "spire": 3.44, "sigil": 2.60,
                     "warden": 4.20, "vealthorn": 0.0, "eilera": 0.0, "karikon": 0.0}
            return table.get(word.lower(), 5.0)

    spellings = {
        form for candidate in find_uncertain_names(turns, lexicon=Wordfreq(), floor=2.0)
        for form in candidate.spellings
    }
    assert {"Vealthorn", "Eilera", "Karikon"} <= spellings
    assert "Bran" not in spellings, "a name that hid in ordinary vocabulary was flagged"
    assert "Warden" not in spellings, "a name built from an English word was flagged"


def test_candidates_are_ordered_with_self_contradiction_first() -> None:
    """Review order is the product decision, so it is asserted rather than incidental."""
    turns = [
        Turn("t0", "Karikon waits."),
        Turn("t1", "Gartog's plan."),
        Turn("t2", "Garthog again."),
    ]
    candidates = find_uncertain_names(turns, lexicon=ORDINARY, floor=2.0)
    assert len(candidates[0].forms) == 2
    assert candidates[0].id == "n0000"


def test_serialisation_carries_the_evidence_not_a_verdict() -> None:
    """Every spelling survives; nothing here picks a winner.

    D-018 keeps entity aliases unresolved because deciding two spellings are one name is
    the question put to a person. A module that resolved it would be inventing the answer
    it exists to ask for.
    """
    turns = [Turn("t0", "Gartog's plan."), Turn("t1", "Garthog again.")]
    payload = find_uncertain_names(turns, lexicon=ORDINARY, floor=2.0)[0].to_dict()
    assert {form["text"] for form in payload["forms"]} == {"Gartog's", "Garthog"}
    assert payload["forms"][0]["turn_ids"]
    assert "canonical" not in payload and "winner" not in payload


def test_the_floor_decides_the_size_of_the_queue() -> None:
    """The floor is the product-facing control, so it needs coverage that can fail.

    `--rarity-floor` is what trades catching one more mangled name against tripling the
    review queue, and that trade is the write-up's central claim. The previous version of
    this test asserted only that `Garthog` was selected at every floor, which is true with
    the argument thrown away entirely -- so the control had no behavioural coverage
    anywhere in the suite.

    Three properties, and the second is the one with teeth:

    * raising the floor never drops anything it already selected;
    * raising it far enough selects strictly more;
    * the words it adds are the ones between the two floors, not arbitrary.

    **Tautology check.** Hardcoding any single floor inside `is_rare`, or ignoring the
    argument, makes this fail: the selections at 3.0 and 4.5 become equal and the strict
    superset assertion goes.
    """
    turns = [
        Turn("t0", "Garthog and the modifier."),
        Turn("t1", "Bran waits by the ridge."),
    ]

    def selected(floor: float) -> set[str]:
        return {
            form
            for candidate in find_uncertain_names(turns, lexicon=ORDINARY, floor=floor)
            for form in candidate.spellings
        }

    # Garthog is absent from the lexicon, so no floor above zero can miss it.
    low, high = selected(3.0), selected(4.5)
    assert low == {"Garthog"}

    # Bran (3.3) and modifier (3.5) sit between the two floors; ridge (4.2) does too,
    # and Garthog stays. Nothing selected at 3.0 is lost at 4.5.
    assert low < high, "raising the floor selected no more than the lower one did"
    assert high == {"Garthog", "Bran", "modifier", "ridge"}


def test_the_floor_is_a_threshold_not_a_rounding() -> None:
    """A word exactly at the floor is common enough to keep out of the queue.

    Stated because the boundary is a product decision rather than an implementation
    detail: `>= floor` means a floor of 3.3 excludes `Bran` and 3.4 includes it.
    """
    turns = [Turn("t0", "Bran waits.")]
    assert find_uncertain_names(turns, lexicon=ORDINARY, floor=3.3) == []
    assert find_uncertain_names(turns, lexicon=ORDINARY, floor=3.4)[0].spellings == ("Bran",)


def test_the_provider_records_that_it_did_not_run_rather_than_an_empty_list() -> None:
    """Zero candidates and no lexicon are different facts and must be distinguishable.

    A consumer reading `candidates: 0` from a provider that was never given a lexicon
    would conclude the recogniser held every name steady, which is the opposite of what
    happened.
    """
    from pathlib import Path

    from rpg_chronicle.transcription.engine import RecognitionResult, RecognizedSegment
    from rpg_chronicle.transcription.provider import SpeechTranscriptProvider

    class Recognizer:
        name = "stub"

        def preflight(self) -> None:
            return None

        def recognize(self, audio: Path) -> RecognitionResult:
            return RecognitionResult(
                segments=[RecognizedSegment(0, 1000, "Garthog waits.")],
                native={},
                confidence_kind="stub probability",
            )

    without = SpeechTranscriptProvider(Recognizer()).transcribe(Path("a.wav"))
    block = without.native_artifact["name_uncertainty"]
    assert block["computed"] is False
    assert block["candidates"] is None, "a count and a list are two answers to one question"
    assert block["detail"] == []
    assert "no lexicon" in block["why_not"]

    with_lexicon = SpeechTranscriptProvider(
        Recognizer(), lexicon=ORDINARY
    ).transcribe(Path("a.wav"))
    block = with_lexicon.native_artifact["name_uncertainty"]
    assert block["computed"] is True and block["candidates"] == 1
    assert block["detail"][0]["forms"][0]["text"] == "Garthog"
    assert "not a confidence" in block["caution"]


def test_preflight_reaches_the_lexicon_before_recognition_runs() -> None:
    """A missing lexicon must cost a second, not twenty minutes of recognition.

    `WordfreqLexicon` loads its table lazily, so without this the first sign of a missing
    dependency is the name pass running *after* the recogniser has finished -- the same
    failure `SpeechTranscriptProvider.preflight` already existed to prevent for the
    diarizer's `soundfile` import.
    """

    from rpg_chronicle.transcription.provider import SpeechTranscriptProvider

    class Recognizer:
        name = "stub"

        def preflight(self) -> None:
            return None

        def recognize(self, audio: Path):  # pragma: no cover - must not be reached
            raise AssertionError("recognition ran before the lexicon was checked")

    class MissingLexicon:
        name = "missing"

        def preflight(self) -> None:
            raise ImportError("wordfreq is not importable")

        def zipf(self, word: str) -> float:  # pragma: no cover
            raise AssertionError("must not be reached")

    provider = SpeechTranscriptProvider(Recognizer(), lexicon=MissingLexicon())
    with pytest.raises(ImportError, match="wordfreq"):
        provider.preflight()

    # A stub lexicon with no preflight of its own is skipped rather than rejected.
    SpeechTranscriptProvider(Recognizer(), lexicon=ORDINARY).preflight()
