"""Point at the names the recogniser probably got wrong, without reading its confidence.

`docs/MILESTONES.md` names important-name uncertainty as an M2 outcome, and it is the one
with a measurement already saying the obvious approach fails. R01 measured turns that
mangled an invented proper noun scoring within 0.02 of a typical turn, which is why
`TranscriptTurn.confidence_kind` carries the standing caution that neither kind finds
entity errors. Nothing in this module reads `confidence`.

## What it uses instead

Two properties, both computed from the transcript alone after recognition has finished.

**Rarity.** A coined name is not in any language model's vocabulary, so the decoder has to
build it from phonemes and emits a string that general English does not contain. This is a
property of the *string*, not of the decoder's certainty about it -- the same word scores
the same whether the engine was sure or guessing.

**Self-contradiction.** A campaign name recurs, and a recogniser that cannot hold it steady
spells it several ways in one session. Two rare spellings that are near-neighbours are far
better evidence than either alone, because ordinary rare words -- `renegotiate`, `bedroll`
-- recur with *identical* spelling. This uses the recording's own internal redundancy, and
it is the component that turns a list of odd strings into a question a person can answer.

Neither is a vote between engines. `research/what-real-recordings-do.md` established that
cross-engine agreement is not accuracy, since engines sharing a lineage mishear alike; no
second engine is consulted here.

## What comes out

A `NameCandidate` is a *cluster of surface forms*, not a per-turn score. That shape is
chosen to match D-018, which says entity aliases accumulate and the canonical spelling is
deliberately left unresolved because *"deciding that two spellings are one name is what
`docs/UX.md` puts in front of a person, and both spellings must survive to be asked."* A
cluster is that question with its evidence already attached.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol

DEFAULT_RARITY_FLOOR = 2.0
"""Zipf frequency below which a token counts as rare.

Measured rather than chosen. On the R02 Hiddengrid window this floor selects 2.3% of turns
and on three Mystic Horizon windows 3.3%; raising it to 3.0 reaches 5.6% and the tokens it
adds are ordinary English (`renegotiate`, `modifier`, `insinuate`) rather than names. The
probe record in `research/probes/` carries the sweep.

Zipf is a log10 scale of occurrences per billion words: 5.0 is `okay`, 3.0 is roughly one
in a million, and 0.0 means the lexicon has never seen the string at all.
"""

MINIMUM_LENGTH = 3
"""Below this, a rare string is more likely a transcription artifact than a name."""

DEFAULT_NEIGHBOUR_DISTANCE = 2
"""The most edits ever allowed between two spellings of one name.

Reached only by strings long enough to afford it -- see `neighbours`. `Gartog` and
`Garthog` differ by one insertion, `Entei` and `Ente` by one deletion, and an hour of the
benchmark recording produced `Gartod`, `Gartok` and `Gartok's` for the same name, all
within one edit of each other.
"""

SHORT_FORM_LENGTH = 6
"""Below this, two forms must be within a single edit to count as one name.

A flat distance of two is meaningless on a short string: it makes `Kat` a neighbour of
`nag`, `Grey` of `goes`, and `Reaper` of `eater`, all of which this probe produced before
the threshold was scaled. A three-letter name has almost every three-letter word inside
two edits, so the tolerance has to grow with the evidence the string carries.
"""


def neighbours(a: str, b: str) -> bool:
    """Whether two spellings are close enough to be one name.

    The tolerance scales with the shorter string because a longer string is more
    distinctive, not less: two edits into a twelve-character name still leaves ten
    characters agreeing, while two edits into a three-character one leaves nothing.
    """
    allowed = 1 if min(len(a), len(b)) < SHORT_FORM_LENGTH else DEFAULT_NEIGHBOUR_DISTANCE
    return _edit_distance(a, b, allowed) <= allowed

_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’]*")

_CLITICS = ("'s", "'ll", "'re", "'ve", "'d", "'m", "n't")


class Lexicon(Protocol):
    """How common a word is in general written and spoken English.

    Injected rather than imported so that this module has no opinion about which lexicon
    is right, and so tests state their own vocabulary instead of depending on whatever
    wordlist the machine running them happens to ship. The lexicon actually used is named
    in the artifact, because a rarity claim means nothing without saying rare *according
    to what*.
    """

    def zipf(self, word: str) -> float:
        """Zipf frequency of `word`, where 0.0 means the lexicon does not contain it."""


class WordfreqLexicon:
    """`wordfreq`'s English frequency table, loaded on first use.

    Chosen over a wordlist because membership is the wrong question. `/usr/share/dict/words`
    was tried first and rejected on measurement: it lacks `okay`, `played`, `box`, `mom` and
    `died`, so almost everything it called unknown was ordinary speech rather than a name.
    A frequency scale separates the two populations cleanly -- ordinary talk sits above 5.0
    and every coined name measured, together with every mangle of one, sits at 0.0.

    Imported lazily and declared in the opt-in `speech` dependency group, so a fixture run
    and CI never pay for it.
    """

    name = "wordfreq (en)"

    def __init__(self) -> None:
        self._zipf = None

    def preflight(self) -> None:
        try:
            from wordfreq import zipf_frequency
        except ImportError as error:
            raise ImportError(
                "name uncertainty needs the 'wordfreq' package, which is not importable. "
                "Install it with `uv sync --group speech`."
            ) from error
        self._zipf = zipf_frequency

    def zipf(self, word: str) -> float:
        if self._zipf is None:
            self.preflight()
        assert self._zipf is not None
        return self._zipf(word, "en")


@dataclass(frozen=True)
class SurfaceForm:
    """One spelling the recogniser produced, and where it produced it."""

    text: str
    occurrences: int
    turn_ids: tuple[str, ...]
    zipf: float


@dataclass(frozen=True)
class NameCandidate:
    """A name the recogniser probably got wrong, as the spellings it actually emitted.

    `forms` carries every spelling rather than a resolved winner. Choosing between them is
    the person's job and the whole point of asking; a module that picked one would be
    inventing the answer it exists to request.
    """

    id: str
    forms: tuple[SurfaceForm, ...]
    occurrences: int
    grounds: str

    @property
    def spellings(self) -> tuple[str, ...]:
        return tuple(form.text for form in self.forms)

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "grounds": self.grounds,
            "occurrences": self.occurrences,
            "forms": [
                {
                    "text": form.text,
                    "occurrences": form.occurrences,
                    "turn_ids": list(form.turn_ids),
                    "zipf": round(form.zipf, 3),
                }
                for form in self.forms
            ],
        }


def _stem(token: str) -> str:
    """Strip the clitic a recogniser attaches to a name, so `Gartog's` reaches `gartog`.

    Without this the possessive is a different string from the bare name and the two never
    cluster -- which on the R02 window would have split the one real self-contradiction
    (`Gartog's` against `Garthog`) into two unrelated singletons.
    """
    low = token.lower().replace("’", "'").strip("'")
    for clitic in _CLITICS:
        if low.endswith(clitic) and len(low) > len(clitic) + 1:
            return low[: -len(clitic)]
    return low


def _edit_distance(a: str, b: str, limit: int) -> int:
    """Levenshtein distance, abandoned once it cannot come in under `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        current = [i]
        for j, cb in enumerate(b, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ca != cb),
                )
            )
        if min(current) > limit:
            return limit + 1
        previous = current
    return previous[-1]


def is_rare(token: str, lexicon: Lexicon, floor: float) -> bool:
    """Whether one token is rare enough in general English to be a name candidate.

    The plural check is what keeps ordinary speech out. A recogniser writes `modifiers`
    and `vegetators`; the first is a common word wearing an `s` and the second is not, and
    only asking about the singular tells them apart.
    """
    stem = _stem(token)
    if len(stem) < MINIMUM_LENGTH or not stem.isalpha():
        return False
    if lexicon.zipf(stem) >= floor:
        return False
    # A regular plural of a common word is not a novel string, and without this every
    # plural the lexicon happens to omit arrives as a name.
    return not (stem.endswith("s") and lexicon.zipf(stem[:-1]) >= floor)


def _cluster(stems: Sequence[str]) -> list[list[str]]:
    """Group rare stems that `neighbours` judges to be one name.

    Single-link agglomeration by union-find. Single-link chains -- a, b and c join when a
    is near b and b near c even if a and c are far apart -- which is correct here: those
    really are successive attempts at one name, and the person is shown every spelling
    anyway rather than a claim about which is right.
    """
    parent = {stem: stem for stem in stems}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    ordered = list(stems)
    for i, a in enumerate(ordered):
        for b in ordered[i + 1 :]:
            if neighbours(a, b):
                union(a, b)

    groups: dict[str, list[str]] = {}
    for stem in ordered:
        groups.setdefault(find(stem), []).append(stem)
    return list(groups.values())


def find_uncertain_names(
    turns: Iterable[object],
    *,
    lexicon: Lexicon,
    floor: float = DEFAULT_RARITY_FLOOR,
) -> list[NameCandidate]:
    """Name candidates for one session, most self-contradicted first.

    `turns` is anything with `id` and `text`, which is `TranscriptTurn` in the product and
    a stub in the tests. The order is the review order: a name the recogniser spelled two
    ways outranks one it spelled oddly but consistently, because the first is evidence the
    engine itself could not decide.
    """
    occurrences: dict[str, dict[str, list[str]]] = {}
    zipfs: dict[str, float] = {}

    for turn in turns:
        turn_id = getattr(turn, "id", None) or ""
        for match in _TOKEN.finditer(getattr(turn, "text", "") or ""):
            token = match.group(0)
            if not is_rare(token, lexicon, floor):
                continue
            stem = _stem(token)
            zipfs.setdefault(stem, lexicon.zipf(stem))
            occurrences.setdefault(stem, {}).setdefault(token, []).append(turn_id)

    candidates: list[NameCandidate] = []
    for group in _cluster(sorted(occurrences)):
        forms: list[SurfaceForm] = []
        for stem in group:
            for text, turn_ids in occurrences[stem].items():
                forms.append(
                    SurfaceForm(
                        text=text,
                        occurrences=len(turn_ids),
                        turn_ids=tuple(turn_ids),
                        zipf=zipfs[stem],
                    )
                )
        forms.sort(key=lambda form: (-form.occurrences, form.text))
        total = sum(form.occurrences for form in forms)
        distinct = len({_stem(form.text) for form in forms})
        grounds = (
            f"the recogniser spelled it {distinct} ways"
            if distinct > 1
            else "no lexicon contains it"
            if forms[0].zipf == 0.0
            else "rare in general English"
        )
        candidates.append(
            NameCandidate(
                id=f"n{len(candidates):04d}",
                forms=tuple(forms),
                occurrences=total,
                grounds=grounds,
            )
        )

    candidates.sort(key=lambda c: (-len({_stem(f.text) for f in c.forms}), -c.occurrences))
    return [
        NameCandidate(id=f"n{index:04d}", forms=c.forms, occurrences=c.occurrences, grounds=c.grounds)
        for index, c in enumerate(candidates)
    ]
