#!/usr/bin/env python3
"""Expand an authored session plan into a four-hour-scale canonical fixture.

Why a generator rather than a committed transcript
--------------------------------------------------

Four hours of play at natural speaking rate is roughly thirty-six thousand words --
about three hundred kilobytes of JSON. That passes the repository's one-mebibyte file
check, but it exceeds the four-hundred-kilobyte diff budget in
`scripts/validate-goal.sh`, so committing it literally would make any goal that
touched it impossible to validate.

The fixture is therefore committed in the form that carries the meaning: an authored
plan holding the story, the dialogue, and the deliberately planted long-range
structure, plus this deterministic expansion. Running it twice on the same plan
produces byte-identical output, so the fixture is reproducible without being resident.

What the expansion actually does
--------------------------------

A real four-hour session is not four hours of plot. It is perhaps forty minutes of
story-bearing dialogue distributed through hours of combat rounds, travel, rules
questions, and conversation about crisps. The plan supplies the story beats; this
script pads each beat out to its share of four hours from that beat's themed filler
pool, interleaving table talk throughout.

The filler is templated, and it repeats more than real play would. It is padding of
the right shape and the right size, not a simulation of a real table. Every number in
this fixture is a measurement of *scale*, never of quality on real play.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

MS_PER_WORD = 400
"""Roughly 150 words per minute, which is unhurried conversational speech."""

GAP_MS = 400
"""Silence between turns. Real sessions have more; this keeps the fixture dense."""

TABLE_TALK_EVERY = 5
"""One turn of out-of-fiction table talk per this many turns of themed filler."""


class PlanError(ValueError):
    """The plan is not usable. Reported with the offending detail, never guessed at."""


def _vary(text: str, step: int) -> str:
    """Deterministically nudge the integers in a filler line.

    Filler pools are finite and a four-hour session needs far more turns than a pool
    holds, so lines recur. Varying the numbers keeps recurrence from becoming verbatim
    blocks -- a dice roll that is nineteen every single time reads as a stuck record
    rather than as a game. Words are never altered: only digits move, and only within
    a range that leaves the sentence sensible.
    """
    if step == 0:
        return text
    out: list[str] = []
    index = 0
    digits = 0
    while index < len(text):
        character = text[index]
        if not character.isdigit():
            out.append(character)
            index += 1
            continue
        end = index
        while end < len(text) and text[end].isdigit():
            end += 1
        value = int(text[index:end])
        digits += 1
        # Small numbers are dice and damage and move freely; large ones are distances
        # and years, where a nudge would contradict the authored story.
        if value <= 24:
            shifted = 1 + (value + step * (digits + 1)) % 24
            out.append(str(shifted))
        else:
            out.append(text[index:end])
        index = end
    return "".join(out)


def _turn(
    turn_id: str,
    speaker: str,
    text: str,
    start_ms: int,
) -> tuple[dict[str, Any], int]:
    words = max(1, len(text.split()))
    duration = words * MS_PER_WORD
    turn = {
        "id": turn_id,
        "start_ms": start_ms,
        "end_ms": start_ms + duration,
        "physical_speaker": speaker,
        # A synthetic transcript claiming perfect confidence would be a lie about the
        # input, and downstream code is entitled to see a realistic spread.
        "confidence": round(0.82 + ((words * 7) % 17) / 100, 2),
        "text": text,
    }
    return turn, start_ms + duration + GAP_MS


def generate(plan: dict[str, Any]) -> dict[str, Any]:
    """Expand a plan into an engine-output fixture the pipeline can consume."""
    speakers = plan.get("speakers")
    beats = plan.get("beats")
    pools = plan.get("filler_pools")
    session = plan.get("session")
    if not isinstance(speakers, dict) or not speakers:
        raise PlanError("plan is missing a non-empty 'speakers' map")
    if not isinstance(beats, list) or not beats:
        raise PlanError("plan is missing a non-empty 'beats' list")
    if not isinstance(pools, dict) or not pools:
        raise PlanError("plan is missing a non-empty 'filler_pools' map")
    if not isinstance(session, dict) or "id" not in session:
        raise PlanError("plan is missing 'session.id'")

    table_pool = pools.get("table")
    if not table_pool:
        raise PlanError("plan needs a 'table' filler pool for out-of-fiction chatter")

    target_total = int(session.get("target_duration_ms", 14_400_000))
    turns: list[dict[str, Any]] = []
    clock = 0
    table_cursor = 0

    for beat_index, beat in enumerate(beats):
        theme = beat.get("filler_theme")
        pool = pools.get(theme)
        if not pool:
            raise PlanError(f"beat {beat.get('id')!r} names unknown filler theme {theme!r}")

        for speaker, text in beat.get("lines", []):
            if speaker not in speakers:
                raise PlanError(f"beat {beat.get('id')!r} uses unknown speaker {speaker!r}")
            turn, clock = _turn(f"turn-{len(turns) + 1:05d}", speaker, text, clock)
            turns.append(turn)

        # Each beat owns an equal share of the session, so the planted callback really
        # does land four hours after the thing it calls back to.
        segment_end = target_total * (beat_index + 1) // len(beats)
        filler_index = 0
        while clock < segment_end:
            if filler_index and filler_index % TABLE_TALK_EVERY == 0:
                speaker, text = table_pool[table_cursor % len(table_pool)]
                step = table_cursor
                table_cursor += 1
            else:
                position = filler_index + beat_index * 7
                speaker, text = pool[position % len(pool)]
                step = position // len(pool)
            if speaker not in speakers:
                raise PlanError(f"filler pool {theme!r} uses unknown speaker {speaker!r}")
            turn, clock = _turn(
                f"turn-{len(turns) + 1:05d}", speaker, _vary(text, step), clock
            )
            turns.append(turn)
            filler_index += 1

    return {
        "session": {
            "id": session["id"],
            "recording": session.get("recording", "synthetic://unknown"),
            "title": session.get("title"),
        },
        "provenance": {
            **plan.get("provenance", {}),
            "generated_from": "benchmarks/fixtures/long_session_plan.json",
            "generator": "scripts/generate_long_session.py",
            "deterministic": True,
        },
        "planted_structure": plan.get("planted_structure", []),
        "engine_output": {
            "engine": "fixture-transcriber",
            "engine_version": "1",
            "turns": turns,
        },
    }


def summarize(fixture: dict[str, Any]) -> dict[str, Any]:
    turns = fixture["engine_output"]["turns"]
    words = sum(len(turn["text"].split()) for turn in turns)
    characters = sum(len(turn["text"]) for turn in turns)
    return {
        "turns": len(turns),
        "words": words,
        "characters": characters,
        "duration_ms": turns[-1]["end_ms"] if turns else 0,
        "duration_hours": round((turns[-1]["end_ms"] if turns else 0) / 3_600_000, 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="generate_long_session",
        description="Expand an authored session plan into a long-form canonical fixture.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path(__file__).parents[1] / "benchmarks" / "fixtures" / "long_session_plan.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text())
    fixture = generate(plan)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n")

    stats = summarize(fixture)
    print(f"wrote {args.output}")
    print(
        f"{stats['turns']} turns, {stats['words']} words, "
        f"{stats['duration_hours']} hours, {stats['characters']} transcript characters"
    )


if __name__ == "__main__":
    main()
