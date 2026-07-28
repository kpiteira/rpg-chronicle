"""Evidence that a vault was not modified, carrying nothing about what is in it.

The obvious method is a per-file manifest, and it is the wrong one here. A manifest is
a list of the operator's note titles, so publishing it as evidence would disclose the
thing the discovery work exists to keep private — the proof and the leak would be the
same document.

What this produces instead is one hex string and three integers. The digest is taken
over each file's relative path *and* its contents, so a rename, an edit, a deletion and
an addition all change it; but the output cannot be read backwards into a path. The
count, the total size and the newest modification time are there so that a difference
says something about what changed rather than only that something did.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .survey import DEFAULT_IGNORED_DIRECTORIES, DEFAULT_IGNORED_FILENAMES

_CHUNK = 1 << 20


@dataclass(frozen=True)
class VaultDigest:
    """A whole-tree fingerprint. Every field is safe to publish."""

    files: int
    total_bytes: int
    newest_mtime: int
    digest: str

    def to_dict(self) -> dict[str, object]:
        return {
            "files": self.files,
            "total_bytes": self.total_bytes,
            "newest_mtime": self.newest_mtime,
            "digest": self.digest,
        }

    def __str__(self) -> str:
        return (
            f"files={self.files} bytes={self.total_bytes} "
            f"newest_mtime={self.newest_mtime}\nsha256={self.digest}"
        )


def vault_digest(
    root: Path,
    *,
    ignored_directories: frozenset[str] = DEFAULT_IGNORED_DIRECTORIES,
    ignored_filenames: frozenset[str] = DEFAULT_IGNORED_FILENAMES,
) -> VaultDigest:
    """Roll the whole tree up into one digest.

    The two exclusion sets default to the application and operating-system state the
    survey also skips — `.obsidian`, which rewrites itself whenever a pane moves, and
    `.DS_Store`, which is rewritten when somebody opens the folder in Finder. Including
    either would report a vault as modified because a person looked at it.

    That is a real gap and worth naming rather than hiding: a change confined to
    Obsidian's own configuration will not be detected. Pass empty sets to cover the whole
    tree when the vault is known to be closed and untouched.
    """
    root = Path(root)
    if not root.is_dir():
        raise NotADirectoryError(f"not a vault directory: {root}")

    rolling = hashlib.sha256()
    files = 0
    total = 0
    newest = 0
    entries = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and not path.is_symlink()
        and path.name not in ignored_filenames
        and not any(part in ignored_directories for part in path.relative_to(root).parts)
    )
    for path in entries:
        per_file = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(_CHUNK):
                per_file.update(chunk)
        stat = path.stat()
        files += 1
        total += stat.st_size
        newest = max(newest, int(stat.st_mtime))
        # Path first, then content. Hashing content alone would call a rename a
        # non-event, and a note moved between folders is a change worth catching.
        rolling.update(path.relative_to(root).as_posix().encode("utf-8"))
        rolling.update(b"\0")
        rolling.update(per_file.digest())
    return VaultDigest(
        files=files, total_bytes=total, newest_mtime=newest, digest=rolling.hexdigest()
    )
