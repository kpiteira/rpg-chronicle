"""Windowing invariants.

Decomposition is the part of this goal most likely to be quietly wrong: a transcript
that mostly fits will exercise the boundary path only on the largest inputs, which are
exactly the ones nobody runs in CI. These tests run the boundary path deliberately.
"""

from __future__ import annotations

import itertools

import pytest

from rpg_chronicle.analysis.decompose import (
    TokenBudget,
    estimate_tokens,
    plan_windows,
    render_turn,
)
from rpg_chronicle.model import TranscriptTurn


def _turns(count: int, words: int = 20) -> list[TranscriptTurn]:
    return [
        TranscriptTurn(
            id=f"turn-{index + 1:05d}",
            start_ms=index * 5000,
            end_ms=index * 5000 + 4000,
            text=" ".join(f"word{index}x{position}" for position in range(words)),
            physical_speaker=f"speaker-{index % 3 + 1}",
        )
        for index in range(count)
    ]


def test_a_transcript_within_budget_is_one_window():
    windows = plan_windows(_turns(10), TokenBudget())
    assert len(windows) == 1
    assert len(windows[0].turns) == 10


def test_no_transcript_at_all_produces_no_windows():
    assert plan_windows([], TokenBudget()) == []


def test_every_turn_appears_in_at_least_one_window():
    """Coverage is the property that matters: a dropped turn is a silently lost scene."""
    turns = _turns(400)
    budget = TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=4)
    covered = {turn.id for window in plan_windows(turns, budget) for turn in window.turns}
    assert covered == {turn.id for turn in turns}


def test_turns_stay_in_order_and_windows_are_contiguous():
    turns = _turns(300)
    budget = TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=0)
    windows = plan_windows(turns, budget)
    flattened = [turn.id for window in windows for turn in window.turns]
    assert flattened == [turn.id for turn in turns]


def test_windows_respect_the_budget_except_where_one_turn_exceeds_it():
    turns = _turns(300)
    budget = TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=2)
    for window in plan_windows(turns, budget):
        size = sum(estimate_tokens(render_turn(turn)) + 1 for turn in window.turns)
        assert size <= budget.transcript_tokens or len(window.turns) == 1


def test_overlap_repeats_the_tail_of_the_previous_window():
    turns = _turns(300)
    budget = TokenBudget(max_input_tokens=4_000, prompt_overhead_tokens=500, overlap_turns=3)
    windows = plan_windows(turns, budget)
    assert len(windows) > 1
    for previous, following in itertools.pairwise(windows):
        shared = {turn.id for turn in previous.turns} & {turn.id for turn in following.turns}
        assert shared, "consecutive windows must share their boundary turns"


def test_a_single_turn_larger_than_the_budget_gets_its_own_window():
    """Truncating a turn would break the evidence contract, so it is not truncated."""
    turns = [
        TranscriptTurn(
            id="turn-00001",
            start_ms=0,
            end_ms=60_000,
            text="word " * 20_000,
            physical_speaker="speaker-1",
        )
    ]
    windows = plan_windows(turns, TokenBudget(max_input_tokens=2_000, prompt_overhead_tokens=500))
    assert len(windows) == 1
    assert windows[0].turns[0].text.startswith("word")


def test_an_oversized_turn_in_the_middle_gets_its_own_window():
    """The oversized-turn rule has to hold wherever the turn falls, not just first.

    With an overlap carry in play the naive loop appends the oversized turn to the
    carried tail, producing a window that both exceeds the budget and holds more than
    one turn -- breaking the promise the docstring makes.
    """
    turns = _turns(40)
    giant = TranscriptTurn(
        id="turn-giant",
        start_ms=10_000_000,
        end_ms=10_060_000,
        text="word " * 20_000,
        physical_speaker="speaker-1",
    )
    turns = turns[:20] + [giant] + turns[20:]
    budget = TokenBudget(max_input_tokens=3_000, prompt_overhead_tokens=500, overlap_turns=4)
    windows = plan_windows(turns, budget)

    holding = [w for w in windows if any(t.id == "turn-giant" for t in w.turns)]
    assert len(holding) == 1
    assert [t.id for t in holding[0].turns] == ["turn-giant"], "it must travel alone"

    for window in windows:
        size = sum(estimate_tokens(render_turn(turn)) + 1 for turn in window.turns)
        assert size <= budget.transcript_tokens or len(window.turns) == 1

    covered = {turn.id for window in windows for turn in window.turns}
    assert covered == {turn.id for turn in turns}


def test_an_oversized_turn_does_not_swallow_the_turns_around_it():
    turns = _turns(10)
    giant = TranscriptTurn(
        id="turn-giant", start_ms=10_000_000, end_ms=10_060_000, text="word " * 20_000
    )
    ordered = plan_windows(
        turns[:5] + [giant] + turns[5:],
        TokenBudget(max_input_tokens=3_000, prompt_overhead_tokens=500, overlap_turns=0),
    )
    flattened = [turn.id for window in ordered for turn in window.turns]
    assert flattened == [turn.id for turn in turns[:5]] + ["turn-giant"] + [
        turn.id for turn in turns[5:]
    ]


def test_a_budget_that_leaves_no_room_for_the_prompt_is_rejected():
    with pytest.raises(ValueError, match="prompt overhead"):
        TokenBudget(max_input_tokens=100, prompt_overhead_tokens=500)


def test_a_rendered_turn_leads_with_its_id_and_names_the_speaker():
    """Every claim cites an id, so the id has to be the most visible thing on the line."""
    turn = _turns(1)[0]
    rendered = render_turn(turn)
    assert rendered.startswith(f"[{turn.id}]")
    assert "(speaker-1)" in rendered


def test_a_turn_without_a_speaker_is_labelled_rather_than_attributed():
    turn = TranscriptTurn(id="turn-00001", start_ms=0, end_ms=1000, text="Something.")
    assert "(unknown-speaker)" in render_turn(turn)
