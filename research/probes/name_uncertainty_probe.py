#!/usr/bin/env python3
"""Measure the name-uncertainty signal against material whose names are known.

Imports the product module rather than reimplementing it. R02's probe and product
disagreed about one attribution figure precisely because the probe carried its own copy of
the rule, and the disagreement was only visible because both numbers happened to be
written down. A probe that measures a copy measures the copy.

What it commits is counts. Materials marked restricted are redacted before `--out` is
written: the selected token types go, and so do the manifest's verified entity labels,
because those live in the content directory with the recording they describe and #35's
constraint is that findings entering the repository are generalisations. The synthetic
clip is exempt because it is rights-clear and already committed with its text.

An earlier version of this file emitted the selected tokens for every material on the
argument that single words are not a transcript. That is true and beside the point: forty
rare words lifted from a redistribution-restricted recording are per-recording material
whether or not they reconstruct a sentence. `--full-out` writes the unredacted copy
outside the checkout, which is R01's `--redact-text` rule applied to a different artifact.

Usage:

    uv run --group speech python research/probes/name_uncertainty_probe.py \\
        --out research/probes/results/name-uncertainty.json \\
        --full-out ~/.rpg-chronicle/probes/name-uncertainty-full.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from rpg_chronicle.transcription.name_uncertainty import (
    _TOKEN,
    SHORT_FORM_LENGTH,
    WordfreqLexicon,
    _stem,
    find_uncertain_names,
    neighbours,
)

ROOT = Path(__file__).resolve().parents[2]
CONTENT_ROOT = Path.home() / ".rpg-chronicle"
CACHE_ROOT = Path.home() / ".cache/rpg-chronicle"

PLANTED_NAMES = ["Vaelthorn", "Ilyra", "Brann", "Korrigan", "Warden"]
"""The coined names R01 planted in the synthetic clip, plus one built from an ordinary word.

`Warden` is here deliberately. `research/probes/score_synthetic.py` separates coined nouns
from names made of English words because scoring them together flatters the result, and
the same separation matters more here: a signal built on rarity *cannot* see `Warden`, and
including it keeps that visible in the numbers instead of leaving it to the prose.
`Ashen Spire` is left out only because this probe scores single-word names.
"""

KNOWN_SUBSTITUTIONS = {
    "Vaelthorn": "Vealthorn",
    "Ilyra": "Eilera",
    "Brann": "Bran",
    "Korrigan": "Karikon",
}
"""What whisper.cpp actually wrote where each planted name belonged.

Published by R01 in `research/probes/results/synthetic-scores.json`, read off the aligned
truth turns rather than guessed here. It matters because two of these substitutions are
**phonetic neighbours and not orthographic ones**: `Ilyra` to `Eilera` and `Korrigan` to
`Karikon` are three or more edits apart, so the edit-distance classifier used on the real
recordings calls them `lost` when the recogniser did not lose them at all -- it replaced
them with something distant. Scoring those by edit distance would have understated the
signal and, worse, hidden the real limitation: selection finds these strings, and linking
them back to one name does not.
"""


@dataclass
class Turn:
    id: str
    text: str
    confidence: float | None = None


def _load_canonical(path: Path) -> list[Turn]:
    payload = json.loads(path.read_text())
    return [
        Turn(id=t["id"], text=t["text"], confidence=t.get("confidence"))
        for t in payload["turns"]
    ]


def _load_whisper_json(path: Path) -> list[Turn]:
    """whisper.cpp `-ojf` output, for a window transcribed outside a pipeline run."""
    payload = json.loads(path.read_text())
    turns: list[Turn] = []
    for index, item in enumerate(payload["transcription"]):
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        scores = [
            token["p"]
            for token in item.get("tokens", [])
            if "p" in token and not str(token.get("text", "")).startswith("[_")
        ]
        turns.append(
            Turn(
                id=f"t{index:05d}",
                text=text,
                confidence=round(sum(scores) / len(scores), 6) if scores else None,
            )
        )
    return turns


def _load_windows(directory: Path) -> list[Turn]:
    """The annotated windows carry a machine draft per segment, not canonical turns."""
    turns: list[Turn] = []
    for path in sorted(directory.glob("w*.json")):
        payload = json.loads(path.read_text())
        for index, segment in enumerate(payload["segments"]):
            turns.append(Turn(id=f"{path.stem}-{index:04d}", text=segment["primary"]))
    return turns


_ARTICLES = {"the", "a", "an"}


def _manifest_names(path: Path) -> list[str]:
    """Verified entity labels that are actually *names* somebody spells.

    The manifests also carry descriptive labels -- "The dragon holding the kidnapped
    target", "the hand axe" -- which are entities but not spellings. An earlier version of
    this filter let them through and then matched them on their first word, so `The tower`
    scored 58 occurrences of the definite article and looked like the best-recognised name
    in the corpus. Anything opening with an article is dropped.
    """
    payload = json.loads(path.read_text())
    names: list[str] = []
    for entity in payload.get("truth", {}).get("important_entities", []):
        if entity.get("status") != "verified":
            continue
        label = str(entity.get("label", "")).strip()
        words = label.split()
        if not words or len(words) > 2 or words[0].lower() in _ARTICLES:
            continue
        names.append(label)
    return names


def _occurrences(turns: list[Turn], name: str) -> int:
    """How often the name appears spelled exactly as the manifest has it."""
    body = " ".join(turn.text for turn in turns).lower()
    return len(re.findall(r"\b" + re.escape(name.lower()) + r"\b", body))


def _confidence_selection(turns: list[Turn], percentile: int) -> set[str]:
    """What a confidence threshold would have put in the review queue.

    Acceptance item 2. The comparison is by *turn*, because that is the only thing a
    confidence threshold can select -- it has no notion of a name.
    """
    scored = [t for t in turns if t.confidence is not None]
    if not scored:
        return set()
    ordered = sorted(scored, key=lambda t: t.confidence or 0.0)
    cut = max(1, len(ordered) * percentile // 100)
    return {t.id for t in ordered[:cut]}


ORDINARY_WORD_ZIPF = 4.0
"""Above this a near-neighbour of a name is an ordinary word, not a mangle of it.

Used only to classify the *truth*, never to select. Without it, `Grey` counts `grew` and
`grow` as manglings of itself and the name looks mangled when it was simply absent. This
is the one place the measurement touches frequency on both sides, and it is why the
classification below is reported as evidence rather than as a reference transcript.
"""


def _classify(turns: list[Turn], name: str, lexicon, substitutions=None) -> dict:
    """What the recogniser actually did to one name, independent of the signal.

    Four outcomes, because scoring against "was the name found" collapses cases that need
    different answers:

    * **clean** -- spelled right, no near-miss anywhere. Flagging it would be noise.
    * **contradicted** -- spelled right *and* spelled wrong elsewhere. The signal's best
      case, and the one the product most wants: the engine disagreed with itself.
    * **replaced** -- never spelled right, but a near-miss is present to point at.
    * **lost** -- never spelled right and nothing resembling it survives. No signal that
      reads the transcript can point at a word the transcript does not contain, and
      counting these as misses of *this* signal would blame it for the recogniser's
      deletion.

    Near-misses are found by edit distance over every token, not over the rare ones, so
    the classification does not assume the answer the signal is being scored on.
    """
    target = _stem(name)
    exact = _occurrences(turns, name)
    variants: dict[str, int] = {}

    declared = (substitutions or {}).get(name)
    if declared is not None:
        # A published correspondence beats inferring one. Used only where R01 recorded
        # what the engine wrote in the name's place; everywhere else the edit-distance
        # path below applies, with the weakness this docstring's `lost` bullet names.
        count = _occurrences(turns, declared)
        return {
            "name": name,
            "outcome": "clean" if exact else ("replaced" if count else "lost"),
            "exact_occurrences": exact,
            "near_misses": {declared: count} if count else {},
            "correspondence": "declared by R01",
            "should_be_flagged": bool(count) and not exact,
        }

    for turn in turns:
        for match in _TOKEN.finditer(turn.text):
            token = match.group(0)
            stem = _stem(token)
            if not stem.isalpha() or stem == target or len(stem) < 3:
                continue
            if not neighbours(stem, target):
                continue
            if lexicon.zipf(stem) >= ORDINARY_WORD_ZIPF:
                continue
            variants[token] = variants.get(token, 0) + 1

    if exact and not variants:
        outcome = "clean"
    elif exact and variants:
        outcome = "contradicted"
    elif variants:
        outcome = "replaced"
    else:
        outcome = "lost"
    return {
        "name": name,
        "outcome": outcome,
        "exact_occurrences": exact,
        "near_misses": variants,
        "should_be_flagged": outcome in ("contradicted", "replaced"),
    }


def measure(label, turns, names, lexicon, floors, substitutions=None, restricted=True) -> dict:
    """One material's results at several floors, plus the confidence comparison."""
    truth = [_classify(turns, name, lexicon, substitutions) for name in names]
    targets = [row for row in truth if row["should_be_flagged"]]

    sweep = {}
    for floor in floors:
        started = time.perf_counter()
        candidates = find_uncertain_names(turns, lexicon=lexicon, floor=floor)
        elapsed_ms = (time.perf_counter() - started) * 1000

        selected_turns = {tid for c in candidates for f in c.forms for tid in f.turn_ids}

        def points_at(name: str, candidates=candidates) -> list[str]:
            """Which candidates carry a spelling of this name.

            Where R01 declared what the engine wrote instead, that exact string is the
            test. Elsewhere it is `neighbours`, which is the same rule the product uses to
            cluster -- so the probe never credits a link the product would not make.
            """
            declared = (substitutions or {}).get(name)
            target = _stem(declared) if declared else _stem(name)
            hits = []
            for candidate in candidates:
                for form in candidate.forms:
                    stem = _stem(form.text)
                    if stem == target or (not declared and neighbours(stem, target)):
                        hits.append(candidate.id)
                        break
            return hits

        flagged = {row["name"]: points_at(row["name"]) for row in targets}
        wrongly_flagged = {
            row["name"]: points_at(row["name"])
            for row in truth
            if row["outcome"] == "clean" and points_at(row["name"])
        }
        sweep[str(floor)] = {
            "candidates": len(candidates),
            "self_contradicted": sum(
                1 for c in candidates if len({f.text.lower() for f in c.forms}) > 1
            ),
            "turns_selected": len(selected_turns),
            "turns_total": len(turns),
            "share_of_turns_selected": round(len(selected_turns) / max(1, len(turns)), 4),
            "wall_ms": round(elapsed_ms, 1),
            "targets": len(targets),
            "targets_flagged": sum(1 for hits in flagged.values() if hits),
            "targets_missed": sorted(n for n, hits in flagged.items() if not hits),
            "clean_names_wrongly_flagged": sorted(wrongly_flagged),
            "candidates_detail": [c.to_dict() for c in candidates],
        }

    confidence = {}
    if any(t.confidence is not None for t in turns):
        default_floor = str(floors[len(floors) // 2])
        signal_turns = {
            tid
            for c in find_uncertain_names(
                turns, lexicon=lexicon, floor=float(default_floor)
            )
            for f in c.forms
            for tid in f.turn_ids
        }
        for percentile in (5, 10, 20):
            picked = _confidence_selection(turns, percentile)
            confidence[f"lowest_{percentile}_percent"] = {
                "turns_selected": len(picked),
                "signal_turns_it_contains": len(picked & signal_turns),
                "signal_turns_total": len(signal_turns),
            }

    return {
        "material": label,
        "restricted": restricted,
        "turns": len(turns),
        "what_the_recogniser_did": truth,
        "outcome_counts": {
            outcome: sum(1 for row in truth if row["outcome"] == outcome)
            for outcome in ("clean", "contradicted", "replaced", "lost")
        },
        "floor_sweep": sweep,
        "confidence_comparison": confidence,
        "short_form_length": SHORT_FORM_LENGTH,
    }


def redacted(material: dict) -> dict:
    """The committable form of a measurement over a recording that cannot be redistributed.

    Counts, shares and timings survive; every string derived from the audio does not.
    That includes the selected token types and the manifest's entity labels -- the labels
    are published truth about the recording, but they live in the content directory with
    the recording precisely because they are per-recording material, and #35's constraint
    is that findings entering the repository are generalisations.

    This is R01's `--redact-text` rule applied to a different artifact, and it is why
    `--full-out` exists: the unredacted copy is written outside the checkout, where the
    numbers can be re-derived without the strings ever being committed.
    """
    if not material["restricted"]:
        return material

    out = dict(material)
    out["redaction"] = (
        "Counts only. Selected token types and verified entity labels are derived from a "
        "redistribution-restricted recording and stay in the content directory; rerun "
        "with --full-out to see them."
    )
    out["what_the_recogniser_did"] = [
        {k: v for k, v in row.items() if k not in ("name", "near_misses")}
        | {"near_miss_count": len(row.get("near_misses", {}))}
        for row in material["what_the_recogniser_did"]
    ]
    out["floor_sweep"] = {
        floor: {
            k: v
            for k, v in row.items()
            if k not in ("candidates_detail", "targets_missed", "clean_names_wrongly_flagged")
        }
        | {
            "targets_missed": len(row["targets_missed"]),
            "clean_names_wrongly_flagged": len(row["clean_names_wrongly_flagged"]),
            "candidate_form_counts": [
                len(c["forms"]) for c in row["candidates_detail"]
            ],
        }
        for floor, row in material["floor_sweep"].items()
    }
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--floors", default="1.0,2.0,3.0")
    parser.add_argument(
        "--full-out",
        type=Path,
        help=(
            "where to write the unredacted copy. Must be outside the checkout: it "
            "carries token types from a restricted recording."
        ),
    )
    parser.add_argument(
        "--long-window",
        type=Path,
        help="whisper.cpp -ojf JSON for a longer window, to show how the queue scales",
    )
    args = parser.parse_args()

    floors = [float(x) for x in args.floors.split(",")]
    lexicon = WordfreqLexicon()
    lexicon.preflight()

    results = []

    # The synthetic clip first, because it is the only material here that is committed,
    # rights-clear and reproducible by anyone. Its names were planted rather than
    # discovered, which makes it the weakest evidence about what a recogniser really
    # fails on and the strongest about whether the signal does what it claims.
    synthetic = ROOT / "research/probes/results/synthetic-whisper-cpp-metal.json"
    if synthetic.is_file():
        payload = json.loads(synthetic.read_text())
        results.append(
            measure(
                "synthetic-table-talk, planted names, whisper.cpp (committed, rights-clear)",
                [
                    Turn(id=t["id"], text=t["text"], confidence=t.get("confidence"))
                    for t in payload["canonical_turns"]
                ],
                PLANTED_NAMES,
                lexicon,
                floors,
                KNOWN_SUBSTITUTIONS,
                restricted=False,
            )
        )

    hiddengrid = (
        CACHE_ROOT / "runs/r02/hiddengrid-swc-ep044-000-600/canonical-session.json"
    )
    if hiddengrid.is_file():
        results.append(
            measure(
                "hiddengrid-swc-ep044, 0-600 s, canonical session from #20",
                _load_canonical(hiddengrid),
                _manifest_names(
                    CONTENT_ROOT
                    / "benchmarks/manifests/hiddengrid-swc-ep044-tower-play.json"
                ),
                lexicon,
                floors,
            )
        )

    if args.long_window and args.long_window.is_file():
        results.append(
            measure(
                f"hiddengrid-swc-ep044, longer window ({args.long_window.name})",
                _load_whisper_json(args.long_window),
                _manifest_names(
                    CONTENT_ROOT
                    / "benchmarks/manifests/hiddengrid-swc-ep044-tower-play.json"
                ),
                lexicon,
                floors,
            )
        )

    mystic = CONTENT_ROOT / "benchmarks/transcripts/mystic-horizon-ch1ep1-killing-zombozos"
    if mystic.is_dir():
        results.append(
            measure(
                "mystic-horizon-ch1ep1, three annotated windows",
                _load_windows(mystic),
                _manifest_names(
                    CONTENT_ROOT
                    / "benchmarks/manifests/mystic-horizon-ch1ep1-killing-zombozos.json"
                ),
                lexicon,
                floors,
            )
        )

    if not results:
        print("no material found; nothing measured", file=sys.stderr)
        return 1

    payload = {
        "probe": "name-uncertainty",
        "lexicon": lexicon.name,
        "output_kind": "model output measured against published manifest truth",
        "caveat": (
            "Verified entity labels come from the benchmark manifests and are "
            "machine-assisted for most items, so they are evidence about which names "
            "exist and not a word-error-rate reference. No recognized speech is "
            "reproduced here; selected rare token types are single words."
        ),
        "materials": results,
    }
    if args.full_out:
        if ROOT in args.full_out.resolve().parents:
            print(f"--full-out {args.full_out} is inside the checkout; refusing", file=sys.stderr)
            return 2
        args.full_out.parent.mkdir(parents=True, exist_ok=True)
        args.full_out.write_text(json.dumps(payload, indent=2) + "\n")
        print(f"wrote {args.full_out} (unredacted)")

    payload = {**payload, "materials": [redacted(m) for m in results]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n")
    print(f"wrote {args.out}")
    for material in results:
        print(f"\n== {material['material']}  ({material['turns']} turns)")
        print(f"   what the recogniser did: {material['outcome_counts']}")
        for floor, row in material["floor_sweep"].items():
            print(
                f"   floor {floor}: {row['candidates']:3d} candidates "
                f"({row['self_contradicted']} self-contradicted), "
                f"{row['share_of_turns_selected']:.1%} of turns, "
                f"{row['wall_ms']:.1f} ms | "
                f"targets {row['targets_flagged']}/{row['targets']} "
                f"missed={row['targets_missed']} "
                f"wrongly_flagged={row['clean_names_wrongly_flagged']}"
            )
        for key, row in material["confidence_comparison"].items():
            print(
                f"   confidence {key}: {row['turns_selected']} turns, contains "
                f"{row['signal_turns_it_contains']}/{row['signal_turns_total']} signal turns"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
