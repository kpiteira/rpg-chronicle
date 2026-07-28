# R03: pointing at the names the recogniser got wrong

Machine: Apple M4 Pro, 24 GB, macOS 26.3.1. Date: 2026-07-28.

> **What this is.** A signal that selects names a recogniser probably mangled, computed
> from the transcript alone, reading no confidence and consulting no second engine.
>
> **What this is not.** A probability that any particular name is wrong. It has no
> calibration, it cannot see a name built from ordinary words, and it cannot see a name the
> recogniser deleted. The section *What it cannot do* is not a disclaimer appended to a
> result; it is half the result.

## Why not confidence

`docs/MILESTONES.md` names important-name uncertainty as an M2 outcome, and it is the one
M2 outcome with a measurement already saying the obvious approach fails. R01 measured turns
that mangled an invented proper noun scoring **within 0.02 of a typical turn**, and above
typical on one stack. `TranscriptTurn.confidence_kind` has carried the standing caution
ever since: *"neither kind finds entity errors."*

That is a claim this goal had to re-test rather than inherit, so it was run again on the
same material the new signal was measured on. It holds, and it is worse than "no better":

| confidence queue | turns it selects | how many of the signal's turns it contains |
|---|---|---|
| lowest 5% | 97 | 3 of 19 |
| lowest 10% | 194 | 6 of 19 |
| lowest 20% | 389 | 7 of 19 |

That is one hour of the benchmark recording. To reach a third of what the new signal
selects, a confidence threshold puts **389 turns** in front of a person. The new signal
selects 19. Confidence is not a cheaper version of this; it is a different and worse
instrument for this job.

## What the signal uses instead

Two properties of the transcript, both computed after recognition has finished, neither
with any access to the decoder.

**Rarity.** A coined name is in no language model's vocabulary, so the decoder builds it
from phonemes and emits a string general English does not contain. This is a property of
the string: the same word scores the same whether the engine was certain or guessing.

**Self-contradiction.** A campaign name recurs, and an engine that cannot hold it steady
spells it several ways in one session. Ordinary rare words — `renegotiate`, `bedroll` —
recur with identical spelling. Two rare spellings that are near neighbours are much better
evidence than either alone, and they are the case the product most wants, because the
engine has already disagreed with itself and a person can settle it in seconds.

An hour of the benchmark recording produced **four spellings of one character's name**,
inside one edit of each other. That is the phenomenon, and nothing about it requires a
second engine — `research/what-real-recordings-do.md` established that cross-engine
agreement is not accuracy, and no second engine is consulted here.

### The output is a cluster, not a score

A candidate is the set of spellings the engine actually emitted, with occurrence counts and
turn ids. Every spelling survives; nothing picks a winner. That follows D-018, which leaves
entity aliases deliberately unresolved because *"deciding that two spellings are one name is
what `docs/UX.md` puts in front of a person, and both spellings must survive to be asked."*
A module that resolved it would be inventing the answer it exists to request.

## What was tried and did not work

Worth more than the one that did, because the next agent will otherwise try them again.

**A wordlist instead of a frequency table.** `/usr/share/dict/words` was the first
instrument and it is unusable. It lacks `okay`, `played`, `box`, `mom`, `died` and `called`,
so on ten minutes of real audio it reported 84 out-of-vocabulary occurrences of which almost
all were ordinary speech. Membership is the wrong question; the right one is *how* rare, and
a frequency scale separates the populations cleanly — ordinary talk above 5.0, every coined
name measured and every mangle of one at 0.0.

**A phonetic key.** Soundex and Metaphone both key on the leading consonant, and the leading
consonant is exactly what these mangles lose: `Vaelthorn` → `Vealthorn`, `Ilyra` → `Eilera`.
A key that starts with the sound the engine got wrong groups nothing.

**A flat edit distance.** Two edits is right for a seven-character name and meaningless for
a three-character one. At a flat two the probe called `nag` a spelling of `Kat`, `goes` a
spelling of `Grey`, and `eater` a spelling of `Reaper`, and each of those became a bogus
target that made the signal look worse than it is. The tolerance now scales with the length
of the string, which is the direction that matches how much evidence a string carries.

**Edit distance as the measure of *whether a name was mangled at all*.** This is the one
that still limits the result. `Ilyra` → `Eilera` and `Korrigan` → `Karikon` are three or
more edits apart: the recogniser did not lose those names, it replaced them with something
orthographically distant but phonetically close. The signal **selects** both strings and
cannot **link** either back to its name. Selection and linking are different problems and
only the first is solved here.

## What it found

Three materials. The synthetic clip is committed and rights-clear; the two recordings are
not, and the committed probe result carries counts only for them.

### The controlled case

`research/probes/results/synthetic-whisper-cpp-metal.json` is whisper.cpp's own transcript
of R01's synthetic clip, which has four planted coined names and one built from an ordinary
word. R01 published what the engine wrote instead, so the correspondence is read rather than
inferred.

| planted | engine wrote | selected? |
|---|---|---|
| Vaelthorn | Vealthorn | yes |
| Ilyra | Eilera | yes |
| Korrigan | Karikon | yes |
| Brann | Bran | **no** |
| Warden | Warden (correct) | no, correctly |

**Three of four.** `Brann` → `Bran` is the miss, and it is the honest one: `Bran` is an
ordinary English word at Zipf 3.30, and a signal built on rarity cannot see a name that
hides inside the vocabulary. `Warden` is not selected because it was not wrong — it is a
name made of an English word, which this signal is blind to in both directions.

These names were planted, which makes this the weakest evidence about what a recogniser
really fails on and the strongest about whether the signal does what it claims.

### The real recordings

Ten minutes and one hour of the benchmark recording, and three annotated windows of a
second one. Names come from the manifests' verified entities, and each was classified by
what the recogniser did to it, independently of the signal:

| outcome | meaning | should the signal flag it? |
|---|---|---|
| clean | spelled right, no near-miss | no |
| contradicted | spelled right *and* spelled wrong elsewhere | yes |
| replaced | never spelled right, a near-miss survives | yes |
| lost | never spelled right, nothing survives | **cannot** |

At the default floor, over one hour: **13 candidates from 1947 turns**, selecting 1.0% of
them, one of which is self-contradicted. It flags the contradicted name and misses the
replaced one. It wrongly flags nothing.

Raising the floor to 3.0 catches the second name and costs 42 candidates, 3.2% of turns, and
one correctly-recognised name flagged as suspect. That trade is why the floor is a flag and
why the default is the lower number: a queue that triples to catch one more name is the
wrong side of *"ask focused questions, never assign proofreading homework."*

**The queue grows sublinearly**, which is the property that makes this usable on a four-hour
recording. At the default floor, six times the audio produced **6 candidates against 13** —
just over twice as many — and the share of turns selected *fell* from 2.3% to 1.0%. Names
recur, and a name spelled five ways is one candidate however often it appears.

Two hours is still not four, and the extrapolation is not offered as one.

### The product path, not just the probe

The probe imports the product module rather than carrying its own copy, so the two cannot
disagree about the rule. They also agree about the result on real audio: a full `run-audio`
run over the ten-minute excerpt produced **6 candidates from 301 turns, one of them
self-contradicted with two spellings** — the same figures the probe reports for the same
window at the same floor. Total wall clock 189 s, against 160 s for the R02 run of the same
excerpt without this pass; the difference is the analysis model's variable network call, not
the 5.5 ms scan.

## Cost

Measured, not estimated, on the hour of audio above.

| | |
|---|---|
| Recognition, same audio | 209 s |
| Lexicon import and load | 60 ms, once per process |
| First scan | 39 ms |
| Steady-state scan, 1947 turns | **5.5 ms** |
| Share of the run | 0.05% |

## What it cannot do

In the same register as the confidence caution it sits beside, because a signal whose limits
live only in a document will be read as having none.

- **It is not a probability of error.** It says a string is rare in general English, or that
  the engine spelled one name several ways. Neither is calibrated and neither should be
  turned into a percentage.
- **A name the recogniser deleted does not appear.** Two of ten verified names in the ten
  minute window, and three of seven in the second recording, left nothing behind at all. No
  signal that reads the transcript can point at a word the transcript does not contain, and
  this one does not pretend otherwise. Whatever addresses that is not a text signal.
- **A name built from ordinary words is invisible.** `Warden`, `Ashen Spire`, `Stuffer
  Shack`, `Grey`. R01 already separated coined nouns from English-word names because scoring
  them together flatters the result; the same separation is why `Warden` is in the table
  above as a name the signal correctly cannot see.
- **It selects strings, it does not link them to names.** `Eilera` is selected; that it is
  `Ilyra` is not something this establishes. Where the mangle is phonetically rather than
  orthographically close, the cluster will hold one spelling and the person gets a smaller
  question than they could have.
- **The lexicon is a dependency with a cultural bias.** Rarity is rare *according to
  `wordfreq`'s English*. A name common in another language, or a real surname at the table,
  will read as rare. The lexicon is named in every artifact for that reason.
- **The evidence is thin on the real material.** Two targets in one recording and none in
  the other, because most verified names were either recognised correctly or deleted
  outright. The synthetic case carries more of the weight than a reader should be
  comfortable with, and the fix is more annotated material rather than more tuning.

## Carried forward

- **A canonical home.** The candidates live in the engine-native artifact, which
  `AnalysisProvider` forbids a consumer from reading — the same gap D-018 closed for
  per-turn quality. The consumer is `docs/ANALYSIS.md`'s alias questions and, after that,
  review-analysis's correction loop (#37). This is the consumer evidence for a session-level
  `name_candidates` collection; the shape is the TPM's to decide, and #33 is how.
- **Linking phonetically distant mangles** is the open half. A phonetic encoder that does not
  key on the leading consonant would be the thing to try, and it should be measured against
  the four spellings the hour of benchmark audio produced.
- **The campaign vocabulary inverts this problem.** Once a name is known, finding its
  manglings is a search rather than a discovery, and `research/what-real-recordings-do.md`
  already says the product *"needs the campaign's own vocabulary, which is what the vault
  eventually supplies."* This signal is what the first session does before that vocabulary
  exists.
