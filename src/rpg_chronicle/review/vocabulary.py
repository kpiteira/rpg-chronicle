"""Approved names, kept across sessions so an answer does not have to be given twice.

`docs/PRODUCT.md` lists "improve from approved vocabulary and speaker corrections" as a
supporting outcome and `docs/UX.md` says corrections "become future vocabulary/context".
This is that store. It holds one kind of knowledge only -- which surface form of a name is
the canonical one, for a given kind of thing -- because that is what a reviewer can settle
in seconds and what the recognizer will get wrong again next week.

Three properties are load-bearing.

**A surface form is matched whole, never partially.** "Ormunt" matches "Ormunt" and does
not match "Ormunt's brother". Substring matching is how one approved spelling silently
rewrites something nobody meant, which the goal names as a risk before any code existed.

**Kind is part of the identity.** A place and a character that share a name are two
things, and `rpg_chronicle.analysis.provider` already refuses to merge across kinds for
the same reason.

**Disagreement is preserved, not resolved.** If one person approves a spelling and a
different person later approves another for the same name, the entry becomes contested
and stops being applied. Overwriting the first approval would be exactly the silent
overwrite of authored content `AGENTS.md` rule 12 forbids; picking the older one would
ignore the newer person; guessing between two people is not the software's call. Both
approvals stay in the file and the name is left alone until a person settles it. One
person changing their own mind is not a disagreement, and supersedes cleanly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STORE_FILENAME = "vocabulary.json"
STORE_SCHEMA_VERSION = "0.1"


class VocabularyError(ValueError):
    """The store on disk is not one this build can safely append to."""


def fold_surface(value: str) -> str:
    """Normalise a surface form for comparison: case and inner whitespace only.

    Shared with `rpg_chronicle.review.apply` deliberately. Two modules deciding
    separately whether "the  Tallow Warden" is the name they already hold is two chances
    to disagree, and the disagreement would show up as a name that never quite matches.
    """
    return " ".join(value.split()).casefold()


@dataclass
class VocabularyEntry:
    kind: str
    canonical: str
    aliases: list[str] = field(default_factory=list)
    approvals: list[dict[str, Any]] = field(default_factory=list)
    contested: bool = False

    def surfaces(self) -> list[str]:
        return [self.canonical, *self.aliases]

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "canonical": self.canonical,
            "aliases": list(self.aliases),
            "contested": self.contested,
            "approvals": list(self.approvals),
        }


@dataclass
class Vocabulary:
    entries: list[VocabularyEntry] = field(default_factory=list)
    schema_version: str = STORE_SCHEMA_VERSION

    # -- reading -------------------------------------------------------------

    def resolve(self, kind: str, surface: str) -> VocabularyEntry | None:
        """The entry claiming this exact surface form for this kind of thing, if one does.

        Two entries claiming the same surface form resolve to nothing. That cannot happen
        through `approve`, which merges overlapping entries, but a hand-edited store can
        contain it, and guessing which of two approvals a name belongs to is worse than
        leaving the name as the model wrote it.
        """
        folded_kind, folded_surface = fold_surface(kind), fold_surface(surface)
        matches = [
            entry
            for entry in self.entries
            if fold_surface(entry.kind) == folded_kind
            and any(fold_surface(item) == folded_surface for item in entry.surfaces())
        ]
        return matches[0] if len(matches) == 1 else None

    # -- writing -------------------------------------------------------------

    def approve(
        self,
        *,
        kind: str,
        canonical: str,
        aliases: list[str],
        approved_by: str,
        approved_at: str,
        session_id: str,
        question_id: str | None = None,
    ) -> VocabularyEntry:
        """Record that a person settled a name, folding it into whatever is already known."""
        folded_kind = fold_surface(kind)
        surfaces = [canonical, *aliases]
        folded_surfaces = {fold_surface(item) for item in surfaces}

        overlapping = [
            entry
            for entry in self.entries
            if fold_surface(entry.kind) == folded_kind
            and folded_surfaces & {fold_surface(item) for item in entry.surfaces()}
        ]
        for entry in overlapping:
            self.entries.remove(entry)

        approvals: list[dict[str, Any]] = []
        known: list[str] = []
        contested = False
        previous_canonicals: set[str] = set()
        for entry in overlapping:
            approvals.extend(entry.approvals)
            known.extend(entry.surfaces())
            contested = contested or entry.contested
            previous_canonicals.add(fold_surface(entry.canonical))

        prior_approvers = {str(item.get("by")) for item in approvals}
        disagrees = bool(previous_canonicals) and previous_canonicals != {fold_surface(canonical)}
        if disagrees and prior_approvers - {approved_by}:
            contested = True

        approvals.append(
            {
                "canonical": canonical,
                "aliases": list(aliases),
                "by": approved_by,
                "at": approved_at,
                "session_id": session_id,
                "question_id": question_id,
            }
        )

        merged: list[str] = []
        for item in [*surfaces, *known]:
            if fold_surface(item) == fold_surface(canonical):
                continue
            if any(fold_surface(item) == fold_surface(existing) for existing in merged):
                continue
            merged.append(item)

        entry = VocabularyEntry(
            kind=kind,
            canonical=canonical,
            aliases=merged,
            approvals=approvals,
            contested=contested,
        )
        self.entries.append(entry)
        return entry

    # -- persistence ---------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> Vocabulary:
        if not path.exists():
            return cls()
        payload = json.loads(path.read_text())
        stored = payload.get("schema_version")
        if stored != STORE_SCHEMA_VERSION:
            raise VocabularyError(
                f"{path} declares vocabulary schema {stored!r}; this build knows "
                f"{STORE_SCHEMA_VERSION!r}."
            )
        entries = [
            VocabularyEntry(
                kind=item["kind"],
                canonical=item["canonical"],
                aliases=list(item.get("aliases", [])),
                approvals=list(item.get("approvals", [])),
                contested=bool(item.get("contested", False)),
            )
            for item in payload.get("entries", [])
        ]
        return cls(entries=entries)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "entries": [entry.to_dict() for entry in self.entries],
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        temporary.replace(path)
