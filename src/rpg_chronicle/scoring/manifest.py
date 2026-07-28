"""Reading a benchmark manifest, from wherever the operator keeps their content.

The manifest is the answer key. It is not in this repository and must not come back
(`docs/CONTENT_AUDIT.md`), so everything here resolves against the content directory and
degrades to a clear message when there is not one -- which is the normal state in CI.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Where recordings, manifests and answer keys live. The same default and the same
#: override as `scripts/validate_benchmark_manifests.py`; duplicated rather than imported
#: because that script is a standalone tool and this is library code, and a package
#: importing from `scripts/` would make the package depend on the repository layout.
CONTENT_ROOT_ENV = "RPG_CHRONICLE_HOME"
DEFAULT_CONTENT_ROOT = Path.home() / ".rpg-chronicle"


class ManifestNotFoundError(FileNotFoundError):
    """Raised when the named manifest is not where the content directory would put it."""


def content_root() -> Path:
    return Path(os.environ.get(CONTENT_ROOT_ENV, DEFAULT_CONTENT_ROOT)).expanduser().resolve()


def manifest_dir(root: Path | None = None) -> Path:
    return (root or content_root()) / "benchmarks/manifests"


def resolve_manifest(reference: str, root: Path | None = None) -> Path:
    """Find a manifest from a path or from a bare manifest id.

    Taking an id keeps the operator from having to know the content directory's internal
    layout to run a score, and taking a path keeps the harness usable against a synthetic
    manifest that lives somewhere else entirely -- which is how the tests run it, and the
    reason the suite needs no content directory.
    """
    candidate = Path(reference).expanduser()
    if candidate.suffix == ".json" or candidate.exists():
        if not candidate.is_file():
            raise ManifestNotFoundError(f"{candidate} is not a file")
        return candidate.resolve()

    directory = manifest_dir(root)
    by_id = directory / f"{reference}.json"
    if not by_id.is_file():
        raise ManifestNotFoundError(
            f"no manifest {reference!r} in {directory}. Manifests and answer keys live "
            f"beside the recordings, outside this repository; set {CONTENT_ROOT_ENV} if the "
            "content directory is not ~/.rpg-chronicle, or pass a path to a manifest file."
        )
    return by_id.resolve()


@dataclass(frozen=True)
class TruthTarget:
    """One item from the answer key, carrying how it was established.

    `basis` and `status` travel with every target because they decide what a score
    against it means. A run that captures four `metadata_inferred` targets and misses
    four `audio_observed` ones has not scored 50%: it has matched the things somebody
    read off a web page and missed the things somebody heard.
    """

    group: str
    index: int
    label: str
    kind: str
    status: str
    basis: str | None
    anchor_ms: int | None
    evidence: str

    @property
    def path(self) -> str:
        return f"truth.{self.group}[{self.index}]"

    @property
    def is_entity(self) -> bool:
        return self.group == "important_entities"


@dataclass(frozen=True)
class NegativeControl:
    """A term the annotator established is *not* in the excerpt.

    The strongest single thing this corpus can measure. Recall needs a judgement about
    whether two sentences say the same thing; a negative control needs only a string
    search, and a system that reports the term is drawing on metadata or on prior
    sessions rather than on the audio it was given.
    """

    term: str
    kind: str
    rationale: str


@dataclass(frozen=True)
class Manifest:
    path: Path
    document: dict[str, Any]

    @property
    def id(self) -> str:
        return self.document["id"]

    @property
    def excerpt_ms(self) -> tuple[int, int]:
        excerpt = self.document["excerpt"]
        return excerpt["start_ms"], excerpt["end_ms"]

    @property
    def excerpt_duration_ms(self) -> int:
        start, end = self.excerpt_ms
        return end - start

    @property
    def annotation_status(self) -> str:
        return self.document.get("references", {}).get("annotation_status", "none")

    @property
    def contaminating_providers(self) -> list[str]:
        return list(self.document.get("truth", {}).get("contaminating_providers") or [])

    @property
    def targets(self) -> list[TruthTarget]:
        truth = self.document.get("truth", {})
        return [
            TruthTarget(
                group=group,
                index=index,
                label=item["label"],
                kind=item["kind"],
                status=item["status"],
                basis=item.get("basis"),
                anchor_ms=item.get("anchor_ms"),
                evidence=item.get("evidence", ""),
            )
            for group in ("important_entities", "important_events")
            for index, item in enumerate(truth.get(group, []))
        ]

    @property
    def negative_controls(self) -> list[NegativeControl]:
        return [
            NegativeControl(
                term=item["term"],
                kind=item.get("kind", "unspecified"),
                rationale=item.get("rationale", ""),
            )
            for item in self.document.get("truth", {}).get("negative_controls") or []
        ]

    def basis_census(self) -> dict[str, int]:
        """How the answer key was established, counted.

        Printed beside every recall number. A reader who sees only the number cannot tell
        a human-heard answer key from one a decoder wrote, and those support very
        different claims.
        """
        census: dict[str, int] = {}
        for target in self.targets:
            key = target.basis or "unstated"
            census[key] = census.get(key, 0) + 1
        return census


def load_manifest(reference: str, root: Path | None = None) -> Manifest:
    path = resolve_manifest(reference, root)
    return Manifest(path=path, document=json.loads(path.read_text(encoding="utf-8")))
