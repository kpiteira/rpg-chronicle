# Vault integration

This document is a **record of what was observed**, not a design. Goal #13 walked one
real Obsidian vault read-only and asked what a campaign-change package would have to
carry to land in it safely. What follows is the vault-neutral part of the answer: the
shapes, and the boundary rules that follow from them.

The per-vault half — folder names, note counts, anything quoted — is deliberately not
here. It describes one person's campaign, so it lives in `~/.rpg-chronicle/vault-discovery/`
for the same reason a per-recording manifest does (`docs/CONTENT_AUDIT.md`,
`docs/GOAL_RULES.md` R1).

## How to read the claims

Every claim carries one of three marks, because an observation from a single vault
presented as an Obsidian convention is a fabrication with a citation.

- **[Obsidian]** — behaviour of the application, true of every vault. Taken from
  Obsidian's documented link semantics; this goal did not run the application to
  re-derive them.
- **[Observed]** — seen in one real vault, n=1. It may be idiosyncratic. It says nothing
  about what other vaults do, and where a magnitude is given it is rounded, with the
  exact figure kept outside the repository.
- **[Inferred]** — a conclusion drawn from an observation, not itself observed. The
  weakest mark, and the one to argue with first.

## Checking this document

The claims below are checkable rather than asserted. `tests/fixtures/synthetic_vault/` is
an invented vault reproducing the observed shapes, and the loader reports them:

```bash
uv run rpg-chronicle vault-survey tests/fixtures/synthetic_vault
```

**Three strengths of check, and they are not interchangeable.** Say which a claim has
before relying on it:

1. **Printed.** Most claims appear as a line in that report, so a reader can hold the two
   side by side. This is the strongest.
2. **Asserted.** Present in the fixture and checked by `tests/test_vault_survey.py`
   without being printed — the session note's narrative-then-roll-up shape is the main
   one, because it is a claim about the *order* of a note's sections rather than a count.
3. **Recorded only.** *What the observed vault did not use* — no tags, callouts, Dataview
   queries or block references — is an observation about absence. The survey does not
   look for any of them, so nothing prints or asserts it, and the fixture's not using
   them demonstrates nothing. It is one vault's style, written down so a later reader
   knows it was checked by eye and not by software.

An earlier draft said "the tests are the union", which was the fourth totalising sentence
in this document to outrun its evidence. They are not: category 3 has no test, by
construction.

The fixture is authored, not redacted — no name, title or phrase in it came from a real
vault. `tests/test_vault_survey.py` executes it.

To evidence that a real vault was not modified, without publishing what is in it:

```bash
uv run rpg-chronicle vault-digest /path/to/vault
```

That prints a file count, a total size, the newest modification time, and one rolled-up
SHA-256 over every file's path and contents. A per-file manifest would be the obvious
method and the wrong one: shown as evidence it would disclose exactly the note titles
this work exists to keep private.

## What a vault is made of

### Notes are typed by their frontmatter, not by their folder

**[Observed]** Most notes open with a YAML frontmatter block, and most carry a `type:`
key naming what the note is — a person, a place, a faction, an object, a rule, a quest.

**[Observed]** The type vocabulary drifts. Singular and plural forms of one type coexist,
as do near-synonyms for one idea. Nothing enforces the set, so it grew rather than being
designed.

**[Observed]** Folders and types cross-cut. One folder holds several declared types, and
one type appears in several folders. Notes of a kind the vault treats as central may
carry no `type:` at all.

**[Inferred]** A consumer must read the declared type where there is one and record its
absence where there is not. Deriving a type from the folder is wrong in both directions,
and normalising the vocabulary would be a change to the operator's own scheme.

### Frontmatter is a convention, and not a schema

**[Observed]** Key sets vary between notes of the same type. A key present on most notes
of a type is absent from some.

**[Observed]** The same key carries different value *shapes* in different notes: a bare
scalar in one, a comma-joined string in another, a YAML block list in a third. Arity is
therefore not a property of the key.

**[Observed]** Some keys hold prose rather than a value — a phrase, a qualification, an
uncertainty the writer wanted to keep.

**[Inferred]** **A tool must not round-trip frontmatter through a YAML serialiser.** Any
serialiser will pick one spelling and rewrite the others on every note it touches, which
is a silent edit to notes the tool was not asked to change. Editing frontmatter means
editing the lines that need editing and leaving the rest byte-for-byte. This is why the
loader in `src/rpg_chronicle/vault/` reads keys and shapes with a line reader and
deliberately does not parse YAML.

### Links are a global namespace of titles

**[Obsidian]** A bare `[[Target]]` resolves against every note in the vault by basename,
regardless of folder. `[[Target|shown text]]` changes the display only. `[[Target#Section]]`
points into a heading. `![[file]]` embeds rather than links.

**[Observed]** Links are overwhelmingly bare. Folder-qualified links may be entirely
absent; piped and heading-anchored links appear but are a small minority; embeds are used
for images and not for notes.

**[Inferred]** **A new note's title is a vault-wide claim.** Creating a note whose
basename matches an existing one makes every bare link to that name ambiguous, silently,
across notes nobody touched. A change package that creates notes must check the whole
vault for a title collision, not the destination folder.

**[Inferred]** Renaming or moving a note is far more dangerous than it looks, and is
outside what a tool should do unprompted.

### A meaningful share of links point at nothing

**[Observed]** Roughly one link in twenty pointed at a note that does not exist. Names
get linked when they come up and written up later, or never.

**[Observed]** Empty notes exist — created so that links to them resolve, holding no
content.

**[Inferred]** **A dangling link is a state, not an error.** A contract that repaired
them would generate notes nobody asked for. **An empty note is not an absent note**: it
records an intention, and filling it in is a proposal like any other rather than a free
action.

### Notes are opened and closed by convention

**[Observed]** A large share of notes open with the same section — an overview — and a
large share close with the same one, a free-text notes section. Between those, section
names recur strongly within a type and are not universal: the most common section of a
type is on nearly every note of it, the next few on most.

**[Inferred]** These are conventions to follow, not a schema to require. Software that
demanded a section would reject notes the operator considers fine.

**[Inferred]** The closing section is the note's own last word. It is a natural place for
a tool to *append* to and a bad place for a tool to write *after*.

### A note accumulates by insertion, not by appending

This is the finding with the most consequence for a change package.

**[Observed]** An entity note records a session's events by gaining a section whose
heading names the session. Notes of every type do this — people, places, objects,
factions, quests.

**[Observed]** Those sections land throughout the note. The largest group sits in the
middle; some sit early; some sit late. Almost none are the last section in their note,
because the closing convention still holds the end.

**[Inferred]** **Appending to the end of the file is the one placement the vault never
uses.** A tool that appends would put its output after the note's closing section, in
the position the convention reserves for nothing.

**[Inferred]** A change package must therefore carry *where* a section belongs, not only
what it says — and "where" cannot be derived from the file, because it is a judgement
about narrative order. This is the strongest argument for the operator previewing and
placing rather than approving a diff.

### A session note has two halves

**[Observed]** A session note carries a bespoke narrative, section by section in play
order, followed by a roll-up block of summary sections — events, rewards, threads left
open, and so on.

**[Observed]** The roll-up's subsection set *grows* between sessions. Later sessions carry
subsections earlier ones do not, added as the campaign found things worth tracking.

**[Observed]** Session frontmatter has a small stable core and an open tail: keys appear
on one session and never again, and singular/plural spellings of one key drift between
sessions.

**[Inferred]** Even the conventional half of a session note is not a fixed template. A
change package should propose a roll-up shape and expect the operator's own to differ.

### The note title and its heading can disagree

**[Observed]** Most notes carry one top-level heading matching the filename. A few do
not — the file was renamed and the heading was not, or the reverse.

**[Obsidian]** Links resolve on the *filename*. Nothing announces the drift.

**[Inferred]** Software must treat the filename as identity and the heading as content.
Correcting one to match the other is an edit to the operator's writing, not a fix.

### What the observed vault did not use

**[Observed]** No tags, no callouts, no Dataview queries, no block references.

**[Inferred]** This is one vault's style and nothing more. It is recorded because
software that *required* any of them would fail here, not because their absence is a
convention. A second vault would very likely use some.

## Where authored content ends and generated content begins

### The observation this rests on is a negative one

**[Observed]** The vault carries **no signal of who wrote what**. Not in frontmatter, not
in the body, not in a sidecar file. Every note looks authored, because every note is a
markdown file with a person's prose in it.

`survey.provenance_signals()` reports it. Be precise about what that buys, because an
earlier draft of this paragraph overstated it and the overstatement is the kind this
repository has a rule against:

- **What is tested.** That the detector recognises a provenance key however it is spelled
  — `test_a_provenance_key_is_recognised_however_it_is_spelled` builds vaults carrying
  `generated-by:` and `Generated By:` and requires both to be found. The mechanism works.
- **What is not.** `test_no_note_carries_a_signal_of_who_wrote_it` runs against the
  *fixture*, whose contents this repository controls. It guards the fixture against
  drifting away from the observed shape. It cannot notice a real vault growing a
  provenance key, and no test can, because no real vault is in CI.
- **What would actually notice.** Running `rpg-chronicle vault-survey` against a vault and
  reading the `provenance` line. The observation is re-checkable on demand; it is not
  continuously monitored, and nothing here should be read as claiming it is.

**[Inferred]** This rules out the shape a reader might expect — inspect a note, decide
whether it looks generated. There is nothing to inspect. The boundary cannot be
*detected*; it can only be *established*, going forward, by the tool.

### The boundary

Stated concretely enough to implement. `src/rpg_chronicle/vault/boundary.py` implements
the classification, and `tests/test_vault_survey.py` exercises it.

**Which rules are code and which are still design**, because "implements exactly this" was
too broad and the difference is what V02 inherits:

| Rule | Status |
|---|---|
| 1, 2, 3, 5, 6, 7, 8 | implemented in `boundary.py` and tested |
| 4 — the record lives outside the vault | **design only.** `GeneratedRegion` is an in-memory dataclass; nothing persists it yet, so nothing enforces where it lives. V02 owns that. |
| "permanently" in rule 5 | **design only.** Reclassification is computed per call from the digest, so a reclaimed region is reclaimed for as long as the edit stands. Making it *permanent* needs the record store rule 4 describes. |

1. **Everything is authored until the tool says otherwise.** Not a cautious default that
   could be relaxed later — the only defensible reading of a vault that predates the tool.
2. **Ownership is per region, not per note.** A region is one section and everything
   under it. Whole-file ownership would either claim notes the operator wrote or be
   useless, because the vault already mixes both inside a single note.
3. **A region is the tool's only if the tool recorded writing it.** The record holds the
   note path, the section title, and a digest of exactly what was written.
4. **The record lives outside the vault.** A marker inside the note would be visible in
   the reader, would travel through the operator's sync, and — worst — would be editable,
   so deleting it would hand the tool permission to overwrite the operator's own writing
   without anyone intending that.
5. **A region a person has edited stops being the tool's, permanently.** The digest no
   longer matches; the region is *reclaimed* and is authored from then on. This is the
   rule that makes the mechanism safe rather than bureaucratic, and it is why the record
   stores a digest and not a flag.
6. **Whitespace alone does not reclaim.** Trailing spaces and a final newline are
   normalised before digesting. An editor's own tidying is not an edit, and treating it
   as one would reclaim every region until the mechanism became noise.
7. **Absence is not permission.** An empty note is authored. A section that does not
   exist is not an empty section the tool may fill.
8. **Losing the records costs the tool its write access and never costs content.** With
   no records, every region classifies as authored. The failure mode is the tool being
   able to do less, which is the correct direction for it to fail in.

### When the two collide

A change package names the regions it wants to write. Before writing anything, the
adapter classifies each one:

- **tool-owned** — replace it.
- **authored** — do not write. Offer it as a proposal beside the existing text.
- **reclaimed** — do not write, and say that the region was the tool's and is not any
  more, because that is information the operator wants rather than a failure.
- **note or section absent** — do not write. Creating something the package believed it
  was updating is the silent surprise this check exists to prevent.

`unsafe_targets()` returns the full list with a reason for each, rather than a boolean.
A caller handed `False` learns to retry; a caller handed a list has to say what it will
do about every entry.

**The collision default is never "overwrite" and never "merge".** It is to propose, which
is what `docs/PRODUCT.md` means by never silently overwriting authored content and what
`AGENTS.md` shared rule 12 requires.

## What the change contract still has to answer

Each of these is open because something observed made it open. They are V02's material,
not this goal's — `docs/STATUS.md` anticipates that split.

1. **How does a package say where a section goes?** Growth is by insertion at a
   semantically right place, and that place is not derivable from the file. Does the
   package carry an anchor ("after this section"), an ordinal, or a proposal the operator
   positions?
2. **What identifies an entity across sessions?** The vault's identity is the filename,
   in one global namespace, with drifting titles and dangling links. Analysis output
   (`entities` and `threads`, D-018) has no such notion. Something has to map one to the
   other, and getting it wrong creates a duplicate note rather than an error.
3. **What happens when a package would create a title that already exists?** A collision
   silently re-points every bare link to that name. Refuse, disambiguate, or ask?
4. **Does a package ever fill an existing empty note?** It is a link target somebody made
   deliberately, so this is a trust question and not a technical one.
5. **May a tool add a frontmatter key?** Key sets already vary per note, so adding one is
   within convention — but it is also the operator's classification scheme, and a key the
   tool relies on is a schema the tool imposed.
6. **What is the unit of rollback?** Per region, per note, or per session package. The
   accumulation pattern touches many notes for one session, so per-note rollback would
   leave a session half-applied.
7. **How is a partial failure reported?** Half a package applied is the worst state, and
   the vault has no transaction.
8. **Which note types may the tool ever write?** A product decision about trust, not a
   technical one. The session note is the obvious candidate because it is created whole;
   an entity note the operator maintains by hand is the obvious counter-candidate.

## The vault-neutral change package

The direction below predates this goal and is unchanged by it. The product should first
produce a structured campaign-change package containing:

- session record;
- scenes;
- new entities;
- proposed entity updates;
- timeline events;
- relationship changes;
- quest changes;
- open questions;
- source evidence;
- confidence and review status.

An Obsidian adapter maps that package into the chosen vault structure. Uncertainty is
resolved before vault application, not discovered inside the vault.

What this goal adds to it: **the package must also carry placement and ownership**, per
the open questions above. A package that says what changed but not where it goes or
whose text it would replace cannot be applied safely, however good the analysis behind it.

## Constraints that hold regardless

- The reference vault is read-only during discovery, and the evidence for that is a
  digest taken before and after, not an assurance.
- Fixtures are authored from a characterisation, never redacted from real content.
  Redaction fails quietly and Git history does not forget.
- No adapter and no code that writes to a vault exists yet. Nothing in
  `src/rpg_chronicle/vault/` opens a file for writing.
