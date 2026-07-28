"""Deciding whether a run found what the answer key says is there.

Every function here is deliberately mechanical. The alternative -- asking a model whether
a scene summary and a truth label describe the same thing -- would make the instrument
depend on the same class of component it is measuring, and a benchmark whose scores move
when its judge is upgraded is not a benchmark.

The price is that these rules are coarse, and the report says so in the words that ship
beside every number. A lexical name match is an upper bound on capture: the name is
present, and whether it is present *as the thing the annotator heard* is not established
here. Anchor corroboration is the matching lower bound. Reporting both, and calling them
what they are, is the honest shape available without a judge.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Dropped before comparing a truth label with an entity name. Truth labels are written as
#: English phrases ("The dragon holding the kidnapped target") and entity names as noun
#: phrases, so the articles are noise on both sides.
STOPWORDS = frozenset({"the", "a", "an", "of", "and"})

#: A candidate shorter than this is not compared. Two-letter tokens collide with ordinary
#: words often enough that a match on one says nothing, and a false capture is the
#: expensive direction of error for a recall number.
MIN_CANDIDATE_CHARS = 3


def normalize(text: str) -> list[str]:
    return [
        token
        for token in re.split(r"[^a-z0-9]+", text.lower())
        if token and token not in STOPWORDS
    ]


def contains_sequence(haystack: list[str], needle: list[str]) -> bool:
    """Whether ``needle`` occurs as a run of consecutive tokens inside ``haystack``."""
    if not needle or len(needle) > len(haystack):
        return False
    for start in range(len(haystack) - len(needle) + 1):
        if haystack[start : start + len(needle)] == needle:
            return True
    return False


def label_matches(label: str, candidate: str) -> bool:
    """Whether a truth label and a proposed name refer to the same thing, lexically.

    Containment is checked both ways on purpose. A truth label is often a description
    around a name -- "The game master, credited by the publisher as nulloperations" -- and
    a model's entity name is often the name with a role attached. Requiring equality would
    score both of those as misses, and the miss would be the instrument's, not the run's.
    """
    label_tokens = normalize(label)
    candidate_tokens = normalize(candidate)
    if not label_tokens or not candidate_tokens:
        return False
    if len("".join(candidate_tokens)) < MIN_CANDIDATE_CHARS:
        return False
    return contains_sequence(label_tokens, candidate_tokens) or contains_sequence(
        candidate_tokens, label_tokens
    )


def mentions(text: str, term: str) -> bool:
    """Whether ``term`` appears in ``text`` as whole tokens.

    Whole tokens rather than a substring: "Mercurial" must not be found inside
    "mercurially", and more to the point a two-token control must not be satisfied by its
    halves appearing in different sentences.
    """
    return contains_sequence(normalize(text), normalize(term))


@dataclass(frozen=True)
class Span:
    start_ms: int
    end_ms: int

    def covers(self, anchor_ms: int) -> bool:
        return self.start_ms <= anchor_ms <= self.end_ms


@dataclass(frozen=True)
class TargetOutcome:
    """What the run did about one truth target.

    Three states rather than hit-or-miss, because the two bounds disagree often enough
    that collapsing them would throw away the diagnosis. `matched_by_name` with
    `anchor_corroborated` false means the run produced the name somewhere other than
    where the annotator heard it -- which is either a second real mention or a
    coincidence, and the harness does not know which.
    """

    path: str
    label: str
    kind: str
    status: str
    basis: str | None
    anchor_ms: int | None
    matched_by_name: bool
    anchor_corroborated: bool
    matched_names: list[str]

    @property
    def missed(self) -> bool:
        return not self.matched_by_name
