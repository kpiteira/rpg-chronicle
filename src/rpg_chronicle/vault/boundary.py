"""Which part of a note is the tool's to touch.

The observation this is built on is a negative one: a vault carries **no signal** saying
who wrote what. Not in frontmatter, not in the body, not in a sidecar. Every note looks
authored because every note is a markdown file with a person's prose in it.

That rules out the shape a reader might expect — inspect a note, decide whether it looks
generated — because there is nothing to inspect. It leaves one workable shape:

1. **Everything is authored until the tool says otherwise.** The default is not a
   cautious setting that could be relaxed later; it is the only defensible reading of a
   vault that predates the tool.
2. **Ownership is per region, not per note.** A vault already accumulates by adding a
   section to a note that is otherwise somebody's own writing, so a rule that could only
   own whole files would either own far too much or be useless.
3. **A region is the tool's only if the tool recorded writing it.** The record lives with
   the tool, outside the vault, and holds a digest of exactly what was written.
4. **A region a human has edited stops being the tool's, permanently.** The digest no
   longer matches; the region is reclaimed. This is the rule that makes the whole thing
   safe, and it is why the record stores a digest rather than a flag.
5. **Absence is not permission.** An empty stub note is authored — somebody created it so
   a link would resolve. Filling it in is a proposal like any other.

None of this writes to a vault, and the functions here answer a question rather than
perform an action. `unsafe_targets` is the check an adapter would run before it did
anything: it names what a change package wants to touch and does not own.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from .survey import Note, Section

_HEADING_LINE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")

AUTHORED = "authored"
"""Written by a person, or old enough that nobody can say otherwise. Never overwritten."""

TOOL_OWNED = "tool-owned"
"""Written by the tool, recorded as such, and unchanged since. Safe to replace."""

RECLAIMED = "reclaimed"
"""The tool wrote it and a person has since edited it. Authored from now on."""


@dataclass(frozen=True)
class GeneratedRegion:
    """The tool's record of one region it wrote.

    Kept outside the vault deliberately. A marker inside the note would be visible in
    the reader, would travel through the operator's own sync, and — worst — would be
    editable, so a person could delete the marker and hand the tool permission to
    overwrite their own writing without ever intending to.

    `content_digest` is over the region body as written. It is what turns "the tool wrote
    this" into "the tool wrote this and nobody has touched it since".
    """

    note_path: str
    section_title: str
    content_digest: str

    @property
    def key(self) -> tuple[str, str]:
        return (self.note_path, self.section_title)


def digest_body(body: str) -> str:
    """Digest a region body, ignoring the whitespace an editor changes on its own.

    Trailing whitespace and a final newline are normalised away. A person who opens a
    note, changes nothing, and lets their editor strip a trailing space has not edited
    the region, and treating that as an edit would reclaim regions until nothing was
    owned and the mechanism became noise.
    """
    normalised = "\n".join(line.rstrip() for line in body.strip().splitlines())
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def section_body(text: str, note: Note, section: Section) -> str:
    """The text belonging to `section`: everything until the next heading of its level or above.

    A subsection is part of its parent, which is what a reader would say too. A `###`
    under a `##` is that `##`'s content, so replacing the `##` region replaces both.

    The section is located by **line number**, not by searching for its title. Searching
    was wrong in a way that matters here: a note holding both `# Foo` and `## Foo`, or the
    same section title twice, would match whichever came first and digest the wrong span —
    so a region could be reported unchanged while its actual text had been edited, which
    is the one failure this module exists to prevent. `Section.line` identifies exactly
    one heading, so there is nothing left to disambiguate.
    """
    lines = text.splitlines(keepends=True)
    index = section.line - 1
    if not 0 <= index < len(lines):  # pragma: no cover - defensive
        raise ValueError(f"section {section.title!r} is not at line {section.line} of {note.path}")

    heading = _HEADING_LINE.match(lines[index])
    if heading is None or heading.group(2).strip() != section.title:
        raise ValueError(  # pragma: no cover - sections come from this same text
            f"line {section.line} of {note.path} is not the heading {section.title!r}"
        )

    start = sum(len(line) for line in lines[: index + 1])
    end = len(text)
    for offset, line in enumerate(lines[index + 1 :], start=index + 1):
        following = _HEADING_LINE.match(line)
        if following and len(following.group(1)) <= section.level:
            end = sum(len(item) for item in lines[:offset])
            break
    return text[start:end]


def classify_region(
    text: str,
    note: Note,
    section: Section,
    records: dict[tuple[str, str], GeneratedRegion],
) -> str:
    """Decide whether one section is `AUTHORED`, `TOOL_OWNED`, or `RECLAIMED`.

    The order of the checks is the safety property: no record at all is answered before
    anything is compared, so a missing, corrupt or lost record can only ever produce
    `AUTHORED`. Losing the record set costs the tool its write access to regions it
    wrote; it never costs the operator their prose.
    """
    record = records.get((note.path, section.title))
    if record is None:
        return AUTHORED
    current = digest_body(section_body(text, note, section))
    return TOOL_OWNED if record.content_digest == current else RECLAIMED


def unsafe_targets(
    sources: dict[str, str],
    notes: dict[str, Note],
    targets: list[tuple[str, str]],
    records: dict[tuple[str, str], GeneratedRegion],
) -> list[tuple[str, str, str]]:
    """The targets a change package must not write, and why.

    `targets` is the (note path, section title) pairs a package intends to replace. The
    result carries one entry per target that is anything other than `TOOL_OWNED`,
    including targets naming a note or a section that does not exist — because creating
    something a package believed it was updating is exactly the silent surprise this
    check exists to prevent.

    Returning the unsafe set rather than a boolean is deliberate: a caller that gets
    `False` learns to retry, and a caller that gets a list has to say what it will do
    about each one.
    """
    problems: list[tuple[str, str, str]] = []
    for note_path, section_title in targets:
        note = notes.get(note_path)
        if note is None:
            problems.append((note_path, section_title, "note does not exist"))
            continue
        section = next(
            (s for s in note.body_sections() if s.title == section_title),
            None,
        )
        if section is None:
            problems.append((note_path, section_title, "section does not exist"))
            continue
        verdict = classify_region(sources[note_path], note, section, records)
        if verdict != TOOL_OWNED:
            problems.append((note_path, section_title, verdict))
    return problems
