"""Fetch a benchmark manifest's media into a private cache and verify it byte for byte.

The manifest records what a fetch returned on a stated date. This script is the procedure
that turns that record into something a second person can reproduce: it downloads the
published media, digests it, and compares the digest and size against the manifest.

A mismatch is a finding, not a nuisance. The source is a 2013 podcast episode served from
the publisher's own host, so bytes that no longer match mean the publisher re-encoded or
replaced the file, and every truth anchor recorded against the old bytes is suspect. The
script therefore refuses to install mismatching bytes as the cached copy and refuses to
rewrite the manifest; it leaves the download beside the target for inspection and tells
the operator to report the difference. Substituting a different source silently would
change the corpus and the licence position without anyone deciding to.

Nothing here writes into the repository: the cache is private, because the media is
copyrighted and must stay outside Git.

Usage:

    uv run python scripts/fetch_benchmark_media.py hiddengrid-swc-ep044-tower-play
    uv run python scripts/fetch_benchmark_media.py --verify-only <manifest-id>

The cache directory comes from ``--cache``, else ``RPG_CHRONICLE_BENCHMARK_CACHE``, else
``benchmark-cache/`` at the repository root. Point the environment variable at the
``paths.benchmark_cache`` you configured in your private ``config/paths.yaml``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = ROOT / "benchmarks/manifests"
DEFAULT_CACHE = ROOT / "benchmark-cache"
CHUNK_BYTES = 1 << 20
USER_AGENT = "rpg-chronicle-benchmark-fetch/0.1 (+https://github.com/kpiteira/rpg-chronicle)"
# The same slug the schema requires of `id`, enforced here because this script will read a
# manifest from anywhere the operator points it.
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Digest:
    """What a file actually is, independent of what any manifest claims."""

    sha256: str
    size_bytes: int


def digest_file(path: Path) -> Digest:
    """Digest a file in chunks, so a multi-hundred-megabyte episode never lands in memory."""
    sha256 = hashlib.sha256()
    size_bytes = 0
    with path.open("rb") as handle:
        while chunk := handle.read(CHUNK_BYTES):
            sha256.update(chunk)
            size_bytes += len(chunk)
    return Digest(sha256.hexdigest(), size_bytes)


@dataclass(frozen=True)
class Comparison:
    """What the bytes turned out to be, against what the manifest claimed.

    Two failures are kept apart because they call for different actions. Bytes that
    disagree with a recorded value mean the source changed under the annotation, and the
    cached copy must not be treated as the item. A manifest that records nothing to check
    against is unverifiable, which is a gap in the manifest -- the bytes may be perfectly
    good, so destroying the cache entry over it would be wrong.
    """

    findings: list[str]
    mismatched: bool


def compare(source: dict, actual: Digest) -> Comparison:
    """Report every way the fetched bytes differ from what the manifest recorded."""
    findings: list[str] = []
    mismatched = False
    expected_sha256 = source.get("media_sha256")
    expected_bytes = source.get("media_bytes")

    if expected_sha256 is None:
        findings.append("manifest records no source.media_sha256, so the fetch cannot be verified")
    elif expected_sha256 != actual.sha256:
        findings.append(f"sha256 is {actual.sha256}, manifest records {expected_sha256}")
        mismatched = True

    if expected_bytes is not None and expected_bytes != actual.size_bytes:
        findings.append(f"size is {actual.size_bytes} bytes, manifest records {expected_bytes}")
        mismatched = True
    return Comparison(findings, mismatched)


def cache_target(cache: Path, manifest: dict) -> Path:
    """Place the media inside the cache, and refuse an id that could climb out of it.

    The script accepts a manifest by path, so the id is not necessarily one this
    repository reviewed. An id such as ``../../ssh`` would otherwise choose where the
    download lands.
    """
    identifier = manifest["id"]
    if not ID_PATTERN.fullmatch(identifier):
        raise ValueError(
            f"manifest id {identifier!r} is not a plain slug; refusing to build a cache "
            "path from it"
        )
    filename = Path(manifest["source"]["media_url"]).name
    if not filename or filename in {".", ".."}:
        raise ValueError(
            f"media_url {manifest['source']['media_url']!r} ends in no usable filename"
        )
    return cache / identifier / filename


def quarantine_path(target: Path) -> Path:
    """Name a quarantine file that does not overwrite evidence from an earlier run."""
    candidate = target.with_suffix(target.suffix + ".mismatch")
    index = 2
    while candidate.exists():
        candidate = target.with_suffix(f"{target.suffix}.mismatch.{index}")
        index += 1
    return candidate


def load_manifest(identifier: str) -> dict:
    """Accept either a manifest id or a path, because both are natural to type."""
    path = Path(identifier)
    if not path.is_file():
        path = MANIFEST_DIR / f"{identifier}.json"
    if not path.is_file():
        raise FileNotFoundError(f"no manifest at {identifier} or {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def cache_dir(explicit: str | None) -> Path:
    """Resolve the private cache, never a repository directory the operator did not choose."""
    if explicit:
        return Path(explicit).expanduser()
    configured = os.environ.get("RPG_CHRONICLE_BENCHMARK_CACHE")
    return Path(configured).expanduser() if configured else DEFAULT_CACHE


def build_request(url: str) -> urllib.request.Request:
    """Ask for the media the way a podcast client would.

    The publisher's host answers urllib's default ``Python-urllib/3.x`` agent with
    HTTP 406, so a procedure that did not set this would be reproducible only in theory.
    """
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def download(url: str, destination: Path) -> None:
    """Stream the media to disk, leaving no partial file behind if the transfer fails.

    The caller verifies the bytes before they are treated as the cached copy.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(build_request(url)) as response, partial.open("wb") as handle:
            while chunk := response.read(CHUNK_BYTES):
                handle.write(chunk)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    partial.rename(destination)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("manifest", help="manifest id (without .json) or path to a manifest")
    parser.add_argument("--cache", help="private cache directory for downloaded media")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="verify the cached copy without fetching anything",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    source = manifest["source"]
    try:
        target = cache_target(cache_dir(args.cache), manifest)
    except ValueError as error:
        print(f"REFUSED: {error}")
        return 1

    if target.exists():
        print(f"cached: {target}")
    elif args.verify_only:
        print(f"missing: {target}")
        print("Nothing to verify. Run without --verify-only to fetch it.")
        return 1
    else:
        print(f"fetching: {source['media_url']}")
        try:
            download(source["media_url"], target)
        except (urllib.error.URLError, OSError) as error:
            print(f"FETCH FAILED: {error}")
            print(
                "The source did not deliver the media. If it is gone rather than "
                "temporarily unreachable, that is a corpus finding: report it on the "
                "benchmark goal issue instead of substituting another source."
            )
            return 1
        print(f"stored: {target}")

    actual = digest_file(target)
    print(f"sha256: {actual.sha256}")
    print(f"bytes: {actual.size_bytes}")

    comparison = compare(source, actual)
    if not comparison.findings:
        print(f"verified: {manifest['id']} matches the manifest")
        return 0

    if not comparison.mismatched:
        # Nothing to check against. The bytes may be fine, so the cached copy is left alone.
        for finding in comparison.findings:
            print(f"UNVERIFIABLE: {finding}")
        print(
            "The download was kept, but nothing establishes that it is the audio the "
            "manifest describes. Record the digest above in the manifest only if you can "
            "vouch for where these bytes came from."
        )
        return 1

    quarantine = quarantine_path(target)
    target.rename(quarantine)
    for finding in comparison.findings:
        print(f"MISMATCH: {finding}")
    print(f"quarantined: {quarantine}")
    print(
        "The published bytes no longer match the manifest. Do not update the recorded "
        "digest and do not substitute another source: report this on the benchmark goal "
        "issue, because every truth anchor was recorded against the old bytes and "
        "replacing the source changes the corpus and its licence position."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
