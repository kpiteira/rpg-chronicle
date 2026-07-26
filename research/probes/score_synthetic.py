#!/usr/bin/env python3
"""Score a probe result against the synthetic clip's declared truth.

Why this is measurement and not a tautology: the truth here is the generator's script,
which no engine ever sees. The engines receive only audio. Comparing what they returned
against what was synthesized is therefore an observation about the engines, not a replay
of a fixture. That distinction is the one ``agents/goal-validator.md`` polices, so it is
worth stating rather than assuming.

What it is still not: a quality benchmark. The clip is noiseless, non-overlapping
text-to-speech. Speaker separation is far easier here than in a room, and the invented
proper nouns are pronounced by a synthesizer rather than by a person. Read these numbers
as sanity and failure-mode evidence.

Usage:
    score_synthetic.py --truth ~/.cache/.../synthetic-table-talk-truth.json \
        --result results/synthetic-parakeet-mlx.json [...] --out results/synthetic-scores.json
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

# Two different things, kept apart on purpose.
#
# COINED are strings no English lexicon contains. A recognizer has to reconstruct them
# from phonemes alone, which is the case the product's campaign vocabulary exists for.
#
# ENGLISH_NAMES are proper nouns built from ordinary words. A recognizer can produce
# them without knowing they are names, so scoring them together with the coined ones
# flatters the result -- "Ashen Spire" recovered says nothing about "Vaelthorn".
COINED_NOUNS = ["Vaelthorn", "Ilyra", "Brann", "Korrigan"]
ENGLISH_NAMES = ["Ashen Spire", "Warden"]
INVENTED_NOUNS = COINED_NOUNS + ENGLISH_NAMES


def _overlap_ms(a_start: int, a_end: int, b_start: int, b_end: int) -> int:
    return max(0, min(a_end, b_end) - max(a_start, b_start))


def score_speakers(truth_turns: list[dict], predicted: list[dict]) -> dict[str, Any]:
    """How well predicted speaker labels line up with the speakers we synthesized."""
    per_turn_purity: list[float] = []
    majority_by_true: dict[str, Counter] = {}

    for turn in truth_turns:
        covered: Counter = Counter()
        for pred in predicted:
            label = pred.get("physical_speaker")
            if not label:
                continue
            covered[label] += _overlap_ms(
                turn["start_ms"], turn["end_ms"], pred["start_ms"], pred["end_ms"]
            )
        total = sum(covered.values())
        if not total:
            per_turn_purity.append(0.0)
            continue
        winner, best = covered.most_common(1)[0]
        per_turn_purity.append(best / total)
        majority_by_true.setdefault(turn["physical_speaker"], Counter())[winner] += best

    # A true speaker split across several clusters is fragmentation; two true speakers
    # sharing one cluster is a collision. They fail the product differently: the first
    # makes a person look like several, the second merges two people into one.
    assignment = {
        true: counts.most_common(1)[0][0] for true, counts in majority_by_true.items() if counts
    }
    collisions = [
        label for label, count in Counter(assignment.values()).items() if count > 1
    ]
    fragmentation = {
        true: len(counts) for true, counts in majority_by_true.items() if len(counts) > 1
    }
    labels = {p["physical_speaker"] for p in predicted if p.get("physical_speaker")}

    return {
        "expected_speakers": len({t["physical_speaker"] for t in truth_turns}),
        "predicted_speaker_labels": len(labels),
        "mean_turn_purity": round(sum(per_turn_purity) / len(per_turn_purity), 3)
        if per_turn_purity
        else None,
        "min_turn_purity": round(min(per_turn_purity), 3) if per_turn_purity else None,
        "dominant_label_per_true_speaker": assignment,
        "colliding_labels": collisions,
        "fragmented_true_speakers": fragmentation,
    }


def score_text(truth_turns: list[dict], turns: list[dict]) -> dict[str, Any]:
    """Targeted lexical check, not word error rate.

    WER needs a normalization policy and a reference corpus that ``benchmarks/`` does
    not have yet. What can be checked honestly today is whether the invented proper
    nouns survived, because those are what a campaign chronicle is made of.
    """
    produced = " ".join(t["text"] for t in turns)
    normalized = re.sub(r"[^a-z ]+", " ", produced.lower())
    found = {noun: noun.lower() in normalized for noun in INVENTED_NOUNS}

    # Ordinary words are the control: if these also fail, the problem is the audio or
    # the pipeline, not the engine's handling of invented vocabulary.
    control = ["perception check", "disadvantage", "courtyard", "ridge"]
    control_found = {phrase: phrase in normalized for phrase in control}

    coined = {n: found[n] for n in COINED_NOUNS}
    english = {n: found[n] for n in ENGLISH_NAMES}

    return {
        # The headline number. Coined strings are the ones a lexicon cannot help with.
        "coined_noun_recall": round(sum(coined.values()) / len(coined), 3),
        "coined_nouns_found": coined,
        # Reported separately so the two are never averaged into one flattering figure.
        "english_word_name_recall": round(sum(english.values()) / len(english), 3),
        "english_word_names_found": english,
        "invented_nouns_found": found,
        "invented_noun_recall": round(sum(found.values()) / len(found), 3),
        "control_phrases_found": control_found,
        "control_phrase_recall": round(sum(control_found.values()) / len(control_found), 3),
        "truth_characters": sum(len(t["text"]) for t in truth_turns),
        "produced_characters": len(produced),
    }


def confidence_vs_errors(truth_turns: list[dict], turns: list[dict]) -> dict[str, Any]:
    """Does confidence separate the turns that got an invented noun from the ones that missed it?

    The product intervenes on low confidence. If a mangled name scores as high as a
    correct one, that intervention rule is blind to the errors that matter most for a
    campaign chronicle -- which is a property of the engine worth knowing before it is
    wired into review prioritization.

    Each truth turn containing an invented noun is located in the output by time
    overlap; the noun either survived in the overlapping text or it did not, and the
    confidences of those overlapping turns go into the corresponding bucket.
    """
    scored = [t for t in turns if t.get("confidence") is not None]
    if not scored:
        return {"available": False}

    hit: list[float] = []
    miss: list[float] = []
    missed_nouns: list[str] = []
    for truth_turn in truth_turns:
        expected = [n for n in INVENTED_NOUNS if n.lower() in truth_turn["text"].lower()]
        if not expected:
            continue
        overlapping = [
            t
            for t in scored
            if _overlap_ms(
                truth_turn["start_ms"], truth_turn["end_ms"], t["start_ms"], t["end_ms"]
            )
            > 0
        ]
        if not overlapping:
            continue
        produced = " ".join(t["text"].lower() for t in overlapping)
        for noun in expected:
            bucket = hit if noun.lower() in produced else miss
            if bucket is miss:
                missed_nouns.append(noun)
            bucket.extend(t["confidence"] for t in overlapping)

    return {
        "available": True,
        "turns_scored": len(scored),
        "overall_min_confidence": round(min(t["confidence"] for t in scored), 4),
        "mean_confidence_where_invented_noun_survived": round(sum(hit) / len(hit), 4)
        if hit
        else None,
        "mean_confidence_where_invented_noun_was_lost": round(sum(miss) / len(miss), 4)
        if miss
        else None,
        "lost_nouns": sorted(set(missed_nouns)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path, nargs="+")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    truth = json.loads(args.truth.read_text())
    truth_turns = truth["turns"]

    scores = {}
    for path in args.result:
        result = json.loads(path.read_text())
        turns = result.get("canonical_turns", [])
        if result["stack"] == "sherpa-diarization":
            # Diarization emits spans without text; score the spans directly.
            spans = result["native_artifact"]["segments"]
            predicted = [
                {
                    "start_ms": round(s["start"] * 1000),
                    "end_ms": round(s["end"] * 1000),
                    "physical_speaker": s["speaker"],
                }
                for s in spans
            ]
            scores[result["stack"]] = {"speakers": score_speakers(truth_turns, predicted)}
            continue
        scores[result["stack"]] = {
            "speakers": score_speakers(truth_turns, turns),
            "text": score_text(truth_turns, turns),
            "confidence": confidence_vs_errors(truth_turns, turns),
        }

    payload = {
        "scored_against": truth["id"],
        "truth_kind": "declared truth, generated locally; no engine saw it",
        "caveat": "Synthetic non-overlapping text-to-speech. Sanity and failure modes "
        "only -- not a quality benchmark and not evidence about room audio.",
        "scores": scores,
    }
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload["scores"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
