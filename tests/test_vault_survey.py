"""The survey, exercised against the synthetic fixture vault.

Every assertion here is about something the *software* derived. None of them restates a
value the fixture declares about itself, which is the tautology `agents/goal-validator.md`
rejects: a test asserting that a note whose frontmatter says `type: npc` has type `npc`
would pass with `survey.py` replaced by a stub that read one line.

The distinction is easiest to see in the negative cases. A dangling link, a title that
no longer matches its own heading, a section that sits in the middle of a note rather
than at the end — the fixture nowhere states any of those. They are conclusions, and each
one requires the loader to have done the work: parse the frontmatter without a YAML
library, resolve links the way Obsidian resolves them, and order sections within a note.

The fixture is invented. It reproduces shapes observed in a real vault and copies nothing
from one; `docs/VAULT_INTEGRATION.md` records which shapes and why each matters.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from rpg_chronicle.vault import (
    AMBIGUOUS,
    AUTHORED,
    RECLAIMED,
    TOOL_OWNED,
    GeneratedRegion,
    classify_region,
    format_report,
    section_body,
    survey_vault,
    unsafe_targets,
    vault_digest,
)
from rpg_chronicle.vault.boundary import digest_body

VAULT = Path(__file__).parent / "fixtures" / "synthetic_vault"


@pytest.fixture(scope="module")
def survey():
    return survey_vault(VAULT)


def test_a_wrong_path_fails_loudly(tmp_path):
    """An empty survey and a mistyped path must not look the same to a caller."""
    with pytest.raises(NotADirectoryError):
        survey_vault(tmp_path / "no-such-vault")


def test_every_markdown_note_is_found(survey):
    assert len(survey.notes) == 36
    assert all(note.path.endswith(".md") for note in survey.notes)


def test_application_state_is_walked_past(tmp_path):
    """Exercised against a vault that actually has an `.obsidian/`, not the fixture.

    The fixture ships none — committing invented Obsidian workspace state would be
    committing noise — so asserting the exclusion against it held vacuously and would
    have passed with the exclusion removed.
    """
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".trash").mkdir()
    (vault / "Real Note.md").write_text("# Real Note\n")
    (vault / ".obsidian" / "notes-in-here-are-not-notes.md").write_text("# Config\n")
    (vault / ".trash" / "Deleted.md").write_text("# Deleted\n")

    found = survey_vault(vault)
    assert [note.path for note in found.notes] == ["Real Note.md"]

    everything = survey_vault(vault, ignored_directories=frozenset())
    assert len(everything.notes) == 3


def test_note_types_come_from_frontmatter_not_from_the_folder(survey):
    """The declared type wins, and a note without one is untyped rather than guessed.

    Both halves matter for a change contract. `Chronicle/` holds notes typed `region`,
    `event`, `historical_event`, `item` and `organization`, so folder-implies-type is
    wrong; and the session notes carry no `type:` at all, so a reader that invented one
    from the folder would be asserting something the vault never said.
    """
    types = survey.note_types()
    assert types["npc"] == 5
    assert types["location"] == 5
    assert types["(untyped)"] == 5

    chronicle = {n.note_type for n in survey.notes if n.folder.startswith("Chronicle")}
    assert len(chronicle) > 1, "one folder holds several declared types"

    sessions = [n for n in survey.notes if n.folder == "Sessions"]
    assert sessions and all(n.note_type is None for n in sessions)


def test_one_key_carries_more_than_one_value_shape(survey):
    """Arity is not a property of a key, so a tool cannot infer it and must not impose it.

    Value shape, not key spelling. The two are separate findings and the earlier name for
    this test blurred them.

    This is the finding that rules out a YAML round-trip: `related_npcs` is a block list
    in one note, a comma-joined string in another and a bare scalar in a third, and any
    serialiser would silently pick one and rewrite the others on every note it touched.
    """
    drift = survey.inconsistent_value_shapes()
    assert "related_npcs" in drift
    assert set(drift["related_npcs"]) == {"block-list", "comma-string", "scalar"}
    assert "affiliation" in drift and "role" in drift


def test_links_resolve_by_basename_across_the_whole_vault(survey):
    """Obsidian's global title namespace, reproduced including its consequence."""
    topology = survey.link_topology()
    assert topology.total > 100
    assert topology.path_qualified == 0, "the fixture links the way the observed vault does"
    assert topology.resolved > topology.unresolved

    linked_from_root = {
        link.basename
        for note in survey.notes
        if note.path == "Chart Room.md"
        for link in note.links
    }
    # Resolved despite living three folders down and never being named with a path.
    assert "Cinder Steps" in linked_from_root
    assert any(n.path == "Chronicle/Places/Cinder Steps.md" for n in survey.notes)


def test_link_topology_counts_each_outcome_itself(tmp_path):
    """`link_topology()`'s own resolved/unresolved/ambiguous counters, pinned exactly.

    The goal validator found this gap by mutation: replacing the classification inside
    `link_topology()` with an unconditional `resolved += 1` left every other test green,
    because `test_some_links_point_at_notes_that_were_never_written` reads
    `unresolved_targets()` — a separate `_stems()` lookup — and only bounds the share from
    above. So the `unresolved` and `ambiguous` figures that `docs/VAULT_INTEGRATION.md`
    asks a reader to check were themselves unchecked.

    Exact equality on a purpose-built vault, because a bound that a stub also satisfies is
    not evidence. Two notes share the stem `Ambiguous` from different folders, which is
    the only way to produce the ambiguous case at all.
    """
    vault = tmp_path / "vault"
    (vault / "a").mkdir(parents=True)
    (vault / "b").mkdir()
    (vault / "Target.md").write_text("# Target\n")
    (vault / "a" / "Ambiguous.md").write_text("# Ambiguous\n")
    (vault / "b" / "Ambiguous.md").write_text("# Ambiguous\n")
    (vault / "Source.md").write_text(
        "# Source\n\n"
        "[[Target]] and [[Target|again]]\n"          # 2 resolved, 1 of them piped
        "[[Never Written]]\n"                        # 1 unresolved
        "[[Ambiguous]]\n"                            # 1 ambiguous
        "[[Target#Some Section]]\n"                  # 1 resolved, anchored
    )

    topology = survey_vault(vault).link_topology()
    assert topology.resolved == 3
    assert topology.unresolved == 1
    assert topology.ambiguous == 1
    assert topology.total == 5
    assert topology.piped == 1
    assert topology.anchored == 1
    assert survey_vault(vault).ambiguous_titles() == ("Ambiguous",)


def test_some_links_point_at_notes_that_were_never_written(survey):
    """Dangling links are ordinary, not damage.

    A vault names a thing before it writes it up. A contract that treated these as
    errors to repair would generate notes nobody asked for, so the count is asserted to
    be non-zero on purpose.
    """
    missing = survey.unresolved_targets()
    assert missing, "the fixture keeps unwritten link targets because real vaults have them"
    assert "The Fifth Keeper" in missing
    assert survey.link_topology().unresolved_share < 0.10

    written = {note.title for note in survey.notes}
    assert not (set(missing) & written), "an unresolved target is one no note answers to"


def test_a_stub_note_is_not_an_absent_note(survey):
    """An empty note is somebody's intention, and filling it in is a different act."""
    stubs = {note.path for note in survey.stubs()}
    assert stubs == {
        "The Ninth Lock.md",
        "Sessions/Session 1 - The Flooded Ledger.md",
    }
    linked = {link.basename for note in survey.notes for link in note.links}
    assert "The Ninth Lock" in linked, "the stub exists because something links to it"


def test_a_note_title_may_disagree_with_its_own_heading(survey):
    """Renaming a file does not rewrite its H1, and links follow the filename.

    Nothing in the vault announces the drift, so software that treated the two as
    interchangeable would be right most of the time and wrong without warning.
    """
    disagreeing = [n for n in survey.notes if n.h1 and not n.title_matches_h1]
    assert len(disagreeing) == 2
    assert {n.title for n in disagreeing} == {"The Ledger Keeper", "The Drowned Ward"}


def test_accumulated_sections_are_not_appended_to_the_end(survey):
    """Where a session-stamped section lands is the finding that rules out appending.

    A note grows by gaining a section *where it belongs in the note's own order*. The
    closing section stays closing. A tool that appended its output to the file would put
    it after the note's last section, which is the one place the convention never uses.
    """
    positions = survey.accumulation_positions()
    assert survey.accumulating_notes()
    assert positions["middle-third"] > positions["last-third"]
    assert positions["final-section-in-note"] == 1, (
        "one note ends on a session section; the exception is in the fixture so that "
        "software cannot assume the closing section is always the same one"
    )
    assert survey.terminal_sections()["Notes"] > positions["final-section-in-note"]


def test_section_conventions_are_conventions_and_not_a_schema(survey):
    """Common enough to rely on, absent often enough that a required section is a bug."""
    recurring = survey.recurring_sections_by_type()
    npc_sections = dict(recurring["npc"])
    assert npc_sections["Overview"] == 5
    assert npc_sections["Background"] < len([n for n in survey.notes if n.note_type == "npc"])

    assert survey.opening_sections()["Overview"] > 1
    assert survey.terminal_sections()["Notes"] > 1


def test_no_note_carries_a_signal_of_who_wrote_it(survey):
    """The observation the whole boundary rests on, pinned for the fixture.

    Be exact about the scope, because an earlier version of this docstring was not. This
    asserts that *the fixture* carries no provenance key, so the fixture cannot drift away
    from the shape it was authored to reproduce. It says nothing about any real vault and
    cannot: no real vault is in CI, and none should be.

    The detector itself is tested separately, by
    `test_a_provenance_key_is_recognised_however_it_is_spelled`. Checking a real vault
    means running `rpg-chronicle vault-survey` against it and reading the `provenance`
    line — on demand, not continuously. `docs/VAULT_INTEGRATION.md` states the same split.
    """
    assert survey.provenance_signals() == ()


def test_a_dot_in_a_note_title_is_not_a_file_extension(tmp_path):
    """`[[Dr. Grey]]` names a note, not a file called `Dr` with a strange suffix.

    Stripping every apparent suffix reported a note that exists as missing, which would
    have shown up downstream as a change package proposing to create it.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "Dr. Grey.md").write_text("# Dr. Grey\n\n## Overview\n\nA note.\n")
    (vault / "Ward.md").write_text("# Ward\n\nSee [[Dr. Grey]] and [[Ward.md]].\n")

    found = survey_vault(vault)
    assert {link.basename for note in found.notes for link in note.links} == {
        "Dr. Grey",
        "Ward",
    }
    assert found.link_topology().unresolved == 0


def test_an_embed_is_an_asset_only_when_it_names_one(tmp_path):
    """`![[Dr. Grey]]` transcludes a note; a dot in a title does not make it a picture.

    The same mistake as `Link.basename` had, in the branch the first fix did not reach.
    Left alone it would have skewed the embed counts in the one direction that matters:
    a note transclusion counted as an image is a link between two notes that the topology
    does not know about.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "art.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (vault / "Dr. Grey.md").write_text("# Dr. Grey\n")
    (vault / "Ward.md").write_text(
        "# Ward\n\n![[art.png]]\n\n![[Dr. Grey]]\n\n![[Dr. Grey.md]]\n"
    )

    topology = survey_vault(vault).link_topology()
    assert topology.embeds_to_asset == 1
    assert topology.embeds_to_note == 2


def test_a_provenance_key_is_recognised_however_it_is_spelled(tmp_path):
    """The negative finding must not be an artefact of matching one spelling.

    The frontmatter reader accepts spaces and hyphens in keys, so a vault writing
    `generated-by:` would have been reported as carrying no provenance signal at all.
    """
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "a.md").write_text("---\ngenerated-by: a tool\n---\n\n# A\n")
    (vault / "b.md").write_text("---\nGenerated By: a tool\n---\n\n# B\n")
    (vault / "c.md").write_text("---\ntype: npc\n---\n\n# C\n")

    signals = survey_vault(vault).provenance_signals()
    assert set(signals) == {"generated-by", "Generated By"}


def test_report_prints_the_claims_a_reader_can_check(survey):
    report = format_report(survey)
    for expected in ("note types", "link topology", "accumulation", "provenance"):
        assert expected in report
    assert str(len(survey.notes)) in report


def test_the_report_is_byte_identical_between_processes():
    """Two runs must produce the same bytes, or it is not evidence.

    `docs/VAULT_INTEGRATION.md` asks a reader to hold this report against a written list
    of claims. Equal counts were previously printed in whatever order a set happened to
    iterate in, which differs per process because of hash randomisation — so two honest
    runs disagreed and a reader had no way to tell that from a real change.

    Run in subprocesses with different seeds on purpose: within one process the seed is
    fixed, so an in-process comparison would pass while the defect was live.
    """
    script = (
        "from pathlib import Path; "
        "from rpg_chronicle.vault import survey_vault, format_report; "
        f"print(format_report(survey_vault(Path({str(VAULT)!r}))), end='')"
    )
    outputs = set()
    for seed in ("0", "1", "12345"):
        environment = {**os.environ, "PYTHONHASHSEED": seed}
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            env=environment,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        outputs.add(result.stdout)
    assert len(outputs) == 1, "the report ordering depends on hash seed"


class TestAuthoredAndGeneratedBoundary:
    """The rules that decide whether a region may be written."""

    @staticmethod
    def _note(survey, path):
        note = next(n for n in survey.notes if n.path == path)
        return note, (VAULT / path).read_text()

    def test_everything_is_authored_without_a_record(self, survey):
        note, text = self._note(survey, "People/Marisol Quay.md")
        section = next(s for s in note.body_sections() if s.title == "Notes")
        assert classify_region(text, note, section, {}) == AUTHORED

    def test_a_recorded_region_is_the_tools_while_it_is_untouched(self, survey):
        note, text = self._note(survey, "People/Marisol Quay.md")
        section = next(s for s in note.body_sections() if s.title == "At the Locks (Session 2)")
        record = GeneratedRegion(
            note_path=note.path,
            section_title=section.title,
            content_digest=digest_body(section_body(text, note, section)),
        )
        assert classify_region(text, note, section, {record.key: record}) == TOOL_OWNED

    def test_an_edited_region_stops_being_the_tools(self, survey):
        """The rule that makes the mechanism safe rather than merely bureaucratic."""
        note, text = self._note(survey, "People/Marisol Quay.md")
        section = next(s for s in note.body_sections() if s.title == "At the Locks (Session 2)")
        record = GeneratedRegion(
            note_path=note.path,
            section_title=section.title,
            content_digest=digest_body("something the tool wrote before a person edited it"),
        )
        assert classify_region(text, note, section, {record.key: record}) == RECLAIMED

    def test_whitespace_alone_does_not_reclaim_a_region(self, survey):
        """Otherwise an editor's own tidying would revoke ownership until none was left."""
        note, text = self._note(survey, "People/Marisol Quay.md")
        section = next(s for s in note.body_sections() if s.title == "At the Locks (Session 2)")
        body = section_body(text, note, section)
        record = GeneratedRegion(note.path, section.title, digest_body(body))
        reflowed = "\n\n" + "\n".join(line + "   " for line in body.splitlines()) + "\n\n"
        assert digest_body(reflowed) == record.content_digest

    def test_a_repeated_section_title_does_not_confuse_the_region(self, tmp_path):
        """Two headings with one title must not be collapsed into whichever came first.

        This is the sharpest failure the module could have. If `section_body` matched by
        title, the digest of the second `## Update` would be taken over the first, so a
        person editing the second would leave the digest unchanged and the region would
        still classify as tool-owned — the tool overwriting somebody's writing while the
        safety check said it was fine.
        """
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "note.md").write_text(
            "# Update\n\ntitle text\n\n"
            "## Update\n\nfirst body\n\n"
            "### Detail\n\nnested\n\n"
            "## Update\n\nsecond body\n"
        )
        found = survey_vault(vault)
        note = found.notes[0]
        updates = [s for s in note.body_sections() if s.title == "Update"]
        assert len(updates) == 2

        first = section_body((vault / "note.md").read_text(), note, updates[0])
        second = section_body((vault / "note.md").read_text(), note, updates[1])
        assert "first body" in first and "nested" in first
        assert "second body" not in first
        assert second.strip() == "second body"
        assert digest_body(first) != digest_body(second)

        # And the H1 sharing the title is a region of its own, not the `##` one.
        title = next(s for s in note.sections if s.level == 1)
        assert "title text" in section_body((vault / "note.md").read_text(), note, title)

    def test_a_duplicate_section_title_is_refused_rather_than_resolved(self, tmp_path):
        """A target naming a title two sections answer to must be refused, not picked.

        This test exists because its previous version was wrong twice over, and both are
        worth keeping visible. It asserted `len(problems) <= 1`, which passes for the empty
        list and would pass with `unsafe_targets` stubbed to return nothing — a tautology.
        And the property it claimed was false: resolving the title to the first match meant
        that when the record digested the *first* of the two sections, `unsafe_targets`
        returned `[]`, which a caller reads as permission to write.

        Both directions are checked, because a refusal that only happens when the
        collision falls one way is not a refusal.
        """
        vault = tmp_path / "vault"
        vault.mkdir()
        source = (
            "# Note\n\n## Update\n\nfirst body\n\n## Keep\n\nother\n\n## Update\n\nsecond body\n"
        )
        (vault / "note.md").write_text(source)
        note = survey_vault(vault).notes[0]
        first, second = (s for s in note.body_sections() if s.title == "Update")
        keep = next(s for s in note.body_sections() if s.title == "Keep")

        for owned in (first, second):
            record = GeneratedRegion(
                note.path, "Update", digest_body(section_body(source, note, owned))
            )
            records = {record.key: record}

            # Handed a specific section, classification is exact: the digest belongs to
            # one span, so the other section is reclaimed rather than mistaken for it.
            verdicts = [
                classify_region(source, note, section, records) for section in (first, second)
            ]
            assert sorted(verdicts) == sorted([TOOL_OWNED, RECLAIMED])

            # Asked to resolve the title itself, the check refuses. Naming the reason
            # exactly is the assertion -- an empty list here is the defect this replaces.
            problems = unsafe_targets(
                {note.path: source},
                {note.path: note},
                [(note.path, "Update")],
                records,
            )
            assert problems == [(note.path, "Update", AMBIGUOUS)]

        # And an unambiguous title in the same note still resolves, so the refusal is
        # about ambiguity rather than the check having become useless.
        owned_keep = GeneratedRegion(
            note.path, "Keep", digest_body(section_body(source, note, keep))
        )
        assert (
            unsafe_targets(
                {note.path: source},
                {note.path: note},
                [(note.path, "Keep")],
                {owned_keep.key: owned_keep},
            )
            == []
        )

    def test_a_region_includes_its_subsections(self, survey):
        """Replacing a `##` replaces the `###`s under it, which is what a reader expects."""
        note, text = self._note(survey, "Crew/Petra Vance.md")
        journey = next(s for s in note.body_sections() if s.title == "Campaign Journey")
        body = section_body(text, note, journey)
        assert "### Session 2" in body and "### Session 4" in body
        assert "## Current Inventory" not in body

    def test_unsafe_targets_names_every_reason_a_write_must_not_happen(self, survey):
        notes = {n.path: n for n in survey.notes}
        sources = {n.path: (VAULT / n.path).read_text() for n in survey.notes}
        marisol = notes["People/Marisol Quay.md"]
        owned = next(s for s in marisol.body_sections() if s.title == "At the Locks (Session 2)")
        record = GeneratedRegion(
            marisol.path,
            owned.title,
            digest_body(section_body(sources[marisol.path], marisol, owned)),
        )

        problems = unsafe_targets(
            sources,
            notes,
            [
                (marisol.path, owned.title),
                (marisol.path, "Notes"),
                (marisol.path, "A Section Nobody Wrote"),
                ("People/Nobody At All.md", "Overview"),
            ],
            {record.key: record},
        )

        assert (marisol.path, owned.title, TOOL_OWNED) not in problems
        assert (marisol.path, "Notes", AUTHORED) in problems
        assert (marisol.path, "A Section Nobody Wrote", "section does not exist") in problems
        assert ("People/Nobody At All.md", "Overview", "note does not exist") in problems

    def test_losing_the_records_costs_write_access_and_never_content(self, survey):
        """Fail-closed, checked by removing the records rather than by asserting the intent."""
        notes = {n.path: n for n in survey.notes}
        sources = {n.path: (VAULT / n.path).read_text() for n in survey.notes}
        targets = [
            (note.path, section.title)
            for note in survey.notes
            for section in note.body_sections()
        ]
        problems = unsafe_targets(sources, notes, targets, {})
        assert len(problems) == len(targets)
        assert {verdict for _, _, verdict in problems} == {AUTHORED}


class TestVaultDigest:
    """The evidence that a vault was not modified, and what it does and does not cover."""

    def test_the_digest_is_stable_across_runs(self):
        assert vault_digest(VAULT) == vault_digest(VAULT)

    def test_the_digest_carries_no_path_from_the_vault(self):
        rendered = str(vault_digest(VAULT))
        for note in survey_vault(VAULT).notes:
            assert note.title not in rendered
        assert "Riverfold" not in rendered

    def test_an_edit_changes_the_digest(self, tmp_path):
        vault = tmp_path / "vault"
        (vault / "sub").mkdir(parents=True)
        (vault / "sub" / "note.md").write_text("# Note\n")
        before = vault_digest(vault)

        (vault / "sub" / "note.md").write_text("# Note\n\nedited\n")
        assert vault_digest(vault).digest != before.digest

    def test_a_rename_changes_the_digest(self, tmp_path):
        """Content-only hashing would call a moved note a non-event."""
        vault = tmp_path / "vault"
        (vault / "sub").mkdir(parents=True)
        (vault / "sub" / "note.md").write_text("# Note\n")
        before = vault_digest(vault)

        (vault / "sub" / "note.md").rename(vault / "sub" / "renamed.md")
        after = vault_digest(vault)
        assert after.digest != before.digest
        assert after.files == before.files and after.total_bytes == before.total_bytes

    def test_a_deletion_changes_the_digest(self, tmp_path):
        vault = tmp_path / "vault"
        vault.mkdir()
        (vault / "a.md").write_text("a\n")
        (vault / "b.md").write_text("b\n")
        before = vault_digest(vault)

        (vault / "b.md").unlink()
        assert vault_digest(vault).digest != before.digest
        assert vault_digest(vault).files == before.files - 1

    def test_application_state_is_excluded_and_saying_so_is_the_point(self, tmp_path):
        """The stated gap, demonstrated: an `.obsidian` change is invisible by default.

        Recorded as a test rather than only as prose because it is the one way this
        evidence can mislead, and a reader is entitled to see its limit exercised.
        """
        vault = tmp_path / "vault"
        (vault / ".obsidian").mkdir(parents=True)
        (vault / "note.md").write_text("# Note\n")
        (vault / ".obsidian" / "workspace.json").write_text("{}")
        (vault / ".DS_Store").write_bytes(b"\x00")
        before = vault_digest(vault)

        (vault / ".obsidian" / "workspace.json").write_text('{"moved": true}')
        (vault / ".DS_Store").write_bytes(b"\x01\x02")
        assert vault_digest(vault) == before

        covered = vault_digest(vault, ignored_directories=frozenset(), ignored_filenames=frozenset())
        assert covered.digest != before.digest
