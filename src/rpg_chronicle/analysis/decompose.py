"""Splitting a transcript that is too large for one request, and putting it back.

This module sees canonical turns and a token budget. It has never heard of a vendor,
an API key, or a CLI. That is the point: adding a backend must not require an edit
here, and changing the windowing must not require an edit to a backend.

The strategy is deliberately simple, because the alternative -- a clever hierarchical
scheme -- would be designed against a predicted problem rather than a measured one.
See `docs/ANALYSIS.md` for what the measurement actually found.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..model import TranscriptTurn

CHARS_PER_TOKEN = 2.5
"""Characters-per-token heuristic used for *planning* only.

Planning happens before any request, so it cannot use a tokenizer the backend owns
without dragging vendor knowledge into this module. Every cost figure this package
reports is the backend's measured count, never this estimate.

The usual rule of thumb for English prose is about four characters per token. This
transcript rendering is nothing like English prose: every line carries a turn id and a
speaker label, and `[turn-02940] (speaker-3)` costs far more tokens per character than
the sentence after it. Measured over the four-hour fixture the real figure was 2.38
characters per token, so a four-character assumption underestimated the request by
1.68x. See `docs/ANALYSIS.md`.

Erring low means planning more windows than strictly needed, which costs a little
money. Erring high means building a request the backend rejects, which costs the whole
run. A backend running near its context limit should lower `max_input_tokens` rather
than trust this constant.
"""


def estimate_tokens(text: str) -> int:
    """Estimate a token count from character length. Planning only, never reported."""
    return math.ceil(len(text) / CHARS_PER_TOKEN)


@dataclass(frozen=True)
class TokenBudget:
    """How much transcript one request may carry.

    `max_input_tokens` is the whole request, so `prompt_overhead_tokens` is subtracted
    to leave room for the instructions wrapped around the turns.

    `overlap_turns` repeats the tail of one window at the head of the next. A scene
    that straddles a boundary is otherwise seen twice in halves and understood
    neither time.
    """

    max_input_tokens: int = 180_000
    prompt_overhead_tokens: int = 2_000
    overlap_turns: int = 8

    def __post_init__(self) -> None:
        if self.max_input_tokens <= self.prompt_overhead_tokens:
            raise ValueError(
                "max_input_tokens must leave room for the prompt overhead: "
                f"{self.max_input_tokens} <= {self.prompt_overhead_tokens}"
            )
        if self.overlap_turns < 0:
            raise ValueError("overlap_turns cannot be negative")

    @property
    def transcript_tokens(self) -> int:
        return self.max_input_tokens - self.prompt_overhead_tokens


@dataclass(frozen=True)
class Window:
    """A contiguous run of turns small enough to analyse in one request."""

    index: int
    turns: list[TranscriptTurn]

    @property
    def turn_ids(self) -> set[str]:
        return {turn.id for turn in self.turns}


def render_turn(turn: TranscriptTurn) -> str:
    """The single rendering of a turn shown to any model.

    The turn id leads the line because every claim the model makes must cite one, and
    a speaker label that looks like a character name is the fastest route to fusing
    physical speakers with fictional characters.
    """
    speaker = turn.physical_speaker or "unknown-speaker"
    return f"[{turn.id}] ({speaker}) {turn.text}"


def render_turns(turns: list[TranscriptTurn]) -> str:
    return "\n".join(render_turn(turn) for turn in turns)


def plan_windows(turns: list[TranscriptTurn], budget: TokenBudget) -> list[Window]:
    """Split turns into windows that fit the budget.

    One window means the transcript fit in a single request; the caller reports that
    as a finding rather than assuming it. A single turn larger than the whole budget
    is placed in a window alone: truncating a turn would break the evidence contract,
    so the request is allowed to fail loudly at the backend instead.
    """
    if not turns:
        return []

    capacity = budget.transcript_tokens
    windows: list[Window] = []
    current: list[TranscriptTurn] = []
    current_tokens = 0

    for turn in turns:
        cost = estimate_tokens(render_turn(turn)) + 1
        if current and current_tokens + cost > capacity:
            windows.append(Window(index=len(windows), turns=current))
            carried = current[-budget.overlap_turns :] if budget.overlap_turns else []
            carried_tokens = sum(estimate_tokens(render_turn(item)) + 1 for item in carried)
            # A carry that fills most of the next window would make every window
            # mostly repeat, so it is dropped rather than allowed to crowd out new
            # material. Continuity is worth less than covering the transcript once.
            if carried_tokens > capacity // 2:
                carried, carried_tokens = [], 0
            current = list(carried)
            current_tokens = carried_tokens
        current.append(turn)
        current_tokens += cost

    if current:
        windows.append(Window(index=len(windows), turns=current))
    return windows
