"""The window transcripts make two claims that can go stale silently, so both are checked.

They are drafts, and the point of committing a draft is that someone later corrects it. Two
things have to survive that: the declaration that they are *not* a reference, which stops a
word error rate being computed against machine output, and the fingerprint digest that says
which recording their timestamps are offsets into.

Neither is checked by the manifest validator, because these are not manifests. Without this
file the digest is copied by hand into three places and verified in none.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_DIR = ROOT / "benchmarks/transcripts"
WINDOWS = sorted(TRANSCRIPT_DIR.glob("*/w*.json"))


def test_there_are_window_transcripts_to_check() -> None:
    """Guards the parametrized tests below, which would all pass on an empty directory."""
    assert WINDOWS, f"no window transcripts found under {TRANSCRIPT_DIR}"


@pytest.mark.parametrize("path", WINDOWS, ids=lambda p: p.name)
def test_a_window_names_the_recording_its_offsets_are_into(path: Path) -> None:
    """The digest is the whole reason the timestamps mean anything.

    A transcript window is a list of offsets, and this source hands out a different file to
    every downloader. The fingerprint is what turns those offsets into positions in a
    recording, so a digest that has drifted from the committed fingerprint leaves a reader
    verifying their copy against a file this transcript was not written for.
    """
    document = json.loads(path.read_text(encoding="utf-8"))
    identity = document["identity"]
    fingerprint = ROOT / identity["content_fingerprint"]

    assert fingerprint.is_file(), identity["content_fingerprint"]
    assert (
        hashlib.sha256(fingerprint.read_bytes()).hexdigest()
        == identity["content_fingerprint_sha256"]
    ), "regenerating the fingerprint means updating every file that records its digest"


@pytest.mark.parametrize("path", WINDOWS, ids=lambda p: p.name)
def test_an_uncorrected_window_refuses_to_be_scored_as_a_reference(path: Path) -> None:
    """Machine output must not be usable as a reference by accident.

    The pairing is what matters and is what could come apart: a corrected transcript may set
    usable_for_word_error_rate, and an uncorrected one may never. Someone marking a window
    corrected without a person having listened, or flipping the usable flag while leaving the
    status alone, is the mistake this exists to stop - it would silently turn agreement with
    large-v3-turbo into an accuracy number.
    """
    document = json.loads(path.read_text(encoding="utf-8"))

    if document["status"] == "uncorrected_machine_draft":
        assert document["usable_for_word_error_rate"] is False
        assert document["why_not"].strip()
    else:
        assert document["status"] == "corrected_by_listener", document["status"]
        assert document.get("correction_method", "").strip(), (
            "a corrected window has to say how the correction was done; a corrector reads "
            "what is written more readily than what was said, and that bounds the result"
        )


@pytest.mark.parametrize("path", WINDOWS, ids=lambda p: p.name)
def test_a_window_carries_the_attribution_its_licence_requires(path: Path) -> None:
    """CC BY 3.0 is what makes committing these lawful, and a file gets copied out of its
    directory, so the obligation has to travel in the file rather than only in the README."""
    attribution = json.loads(path.read_text(encoding="utf-8"))["attribution"]

    for field in ("work", "author", "source", "license", "license_url", "modification"):
        assert attribution.get(field, "").strip(), field
