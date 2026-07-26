# Annotation record: Hiddengrid EP044, 0–600 s

Manifest: [`../manifests/hiddengrid-swc-ep044-tower-play.json`](../manifests/hiddengrid-swc-ep044-tower-play.json)
Annotated: 2026-07-26. Goal: B02 (issue #11).

This file is the working record behind that manifest: how the audio was obtained, what it
measurably is, why the excerpt window was kept where it is, how the truth targets were
established, and — the part that matters most before anyone reports a number — what a
score against this item does and does not demonstrate.

No audio, clip, derivative, or transcript of this episode is in the repository. Quotations
here are the short fragments needed to anchor a target, attributed to the source.

## Fetching it again

```bash
export RPG_CHRONICLE_BENCHMARK_CACHE=/your/private/benchmark/cache   # paths.benchmark_cache
uv run python scripts/fetch_benchmark_media.py hiddengrid-swc-ep044-tower-play
```

The script downloads `source.media_url` into `<cache>/<manifest id>/`, digests it, and
compares the digest and byte count with `source.media_sha256` and `source.media_bytes`.
A cached copy is verified in place; `--verify-only` never fetches.

Expected on success:

```text
sha256: 2a0f5272568b772fe9bcfd9371231484b153dc79e755564490a69b2552ac37e9
bytes: 127266240
verified: hiddengrid-swc-ep044-tower-play matches the manifest
```

**When the bytes differ.** The script renames the download to `*.mismatch`, prints each
difference, and exits non-zero. Do not update the recorded digest, and do not substitute
another source. Every time anchor in the manifest is an offset into *these* bytes: a
re-encode shifts them, and a replaced file invalidates them entirely. Report the
difference on the benchmark goal issue with the new digest, the new byte count, and the
HTTP `Last-Modified` header, and let the corpus decision — including its licence position
— be made deliberately. On 2026-07-26 the publisher's host returned the recorded bytes
unchanged, with `Last-Modified: Sat, 24 May 2014 18:53:35 GMT`.

## What the audio measurably is

| Property | Value | How it was established |
|---|---|---|
| Container | MP3, 128 kbit/s CBR, 7954.009 s | `ffprobe` |
| Sampling | 16 kHz, nominally 2 channels | `ffprobe` |
| Channel content | one mixed track; L−R residual is 34 dB below programme | `ffmpeg pan` + `astats` |
| Bandwidth | nothing above 8 kHz; energy above 7 kHz is 26 dB down | `astats` with and without a 7 kHz high-pass |
| Loudness | −19.2 LUFS integrated, 8.2 LU range, true peak +0.2 dBFS | `ebur128` |
| Gap floor | 1.05% of window samples exactly zero, 4.6% below −78 dBFS | raw sample histogram |
| Music | 00:00:03–00:00:57, welcome from 00:00:28 over it | `silencedetect` at −40 dB, checked on a spectrogram |

The commands and their raw output are committed alongside this file, in
[`hiddengrid-swc-ep044-measurements.md`](hiddengrid-swc-ep044-measurements.md), so the
table above can be checked without re-fetching 127 MB.

Two consequences worth carrying forward. The single mixed track means **there is no
per-speaker channel**: any diarization probed here works from one signal, as it would on
the target iPad recording. And the gated near-silence between utterances, together with
post-production levelling and limiting, means this is a **produced** artifact — it is not
the raw acoustic condition the product is aimed at, and it should not be read as a proxy
for one.

What is *not* measurable here is where the speakers were sitting. The gating rules out a
raw single-room capture, and the publisher's online-play format, the players referred to
by handle, and one player being "AFK" at 00:17:00 all point to remote play — but that is
inference from the publisher and the content, not from the signal. So
`capture_layout` records `single_mixed_track`, which is the measured part, and the remote
reading stays here in prose with its evidence attached. An enum value claiming "remote"
would have smuggled an inference into the field a consumer is most likely to read alone,
which is the same mistake the `basis` split exists to prevent.

## Why the window stayed at 0–600 000 ms

The goal allowed moving it if the default proved to be intro music and recap. Measured, it
is not: music occupies 54 s of the 600 s, the recap ends at 1:50, and the remaining ~82%
is live play. The window was kept, and it earns its place on diagnostic variety rather
than plot density — the denser plot is at 20–30 min, where the group's pay is
renegotiated. Inside 0–600 s the window offers, in one span:

- speech mixed with music for its first 29 s of talking;
- a recap that states prior-session events *inside* the window;
- an explicit player-to-character mapping spoken aloud ("Ante's character, James", 00:03:42);
- a relayed in-fiction phone call, where the speaker and the character being spoken for diverge;
- setting vocabulary that both reference decoders got wrong (nuyen, Stuffer Shack);
- a title entity, Maria Mercurial, whose surname appears in no decode of the window.

## Who is speaking

Seven distinct first-person speaking roles are heard in the window: the game master, and
the players of Kat, Pulse, James, Grey, Freya and Gartog. How many *people* hold those
roles is a separate question, and this is where an earlier draft of this file got it
wrong — worth recording, because the error is an easy one and the correction is the
whole point of a "proven" number.

Four exchanges put two roles in immediate succession, which establishes those two as
different people: Kat with Pulse at 00:02:35, Kat with James at 00:04:04, James with Grey
at 00:04:10, Freya with the game master at 00:05:51. The draft read that as proving five
distinct people. It does not. Those are four *pairwise* constraints, and no three of the
roles are ever established as pairwise distinct among themselves, so the whole set is
satisfiable by two people:

| Person | Roles |
|---|---|
| one | Freya, Grey, Kat |
| two | game master, James, Pulse |

Nothing in the recorded evidence rules that out. Counting the roles that appear in the
pair evidence is not the same as counting the people it separates — proving *k* distinct
people needs *k* roles that are pairwise distinct from each other, and the largest such
set here is 2.

**So: 7 roles heard, 2 people demonstrated.** Both numbers are in the manifest, as
`expected_physical_speakers` and `proven_distinct_speakers`, so neither has to be read
out of prose. The true count is very probably 6 or 7 — the publisher tags five player
handles for this episode and there is a host — but that is inference from metadata and
content, not something this recording demonstrates. Raising the floor honestly needs
overlapping speech or voice-print separation, and neither was performed.

Characters outnumber speakers, which is the point. Kiko exists in the fiction behind a
closed door while the player is away from the keyboard (00:17:00, outside the window), and
the episode's central NPC is discussed by people who are not voicing her. The window also
contains the separation stated explicitly rather than merely implied: one player, phoning
another, names the person and the character in the same sentence.

Physical speakers are recorded in the manifest as `kind: person` and characters as
`kind: character`. Two people are identifiable by name from the audio: **Jacob**
(addressed at 00:01:09) and **Entei** (the handle at 00:03:42, spelled from the
publisher's episode tags — the decodes hear "Ante"). The publisher tags this episode
Andrew, Dan, Entei, Midas and Samons, five handles for what sounds like six players plus
the host; the mapping from handles to voices was not attempted and is not claimed.

## How the truth was made, and what that costs

**Machine-assisted listen-through, not a human ear.** The window was decoded twice, by
different implementations and model families, both running locally on the private copy:

- whisper.cpp `large-v3-turbo`, beam size 5;
- openai-whisper `medium.en`.

The exact invocations, so a second person can re-derive the reading rather than
reconstruct the pipeline by guesswork. `$WAV` is the 16 kHz mono decode described in
[`hiddengrid-swc-ep044-measurements.md`](hiddengrid-swc-ep044-measurements.md); the ggml
models are the standard whisper.cpp conversions, and `openai-whisper` fetches its own
weights on first use.

```bash
# The two window decodes that a target has to appear in to be verified
whisper-cli -m ggml-large-v3-turbo.bin -f $WAV -l en \
    --offset-t 0 --duration 600000 -bs 5 -ojf -of window_turbo
whisper $WAV --model medium.en --language en --clip_timestamps 0,600 \
    --output_format json --fp16 False

# Consulted on contested passages only, after cutting the passage from $WAV
whisper-cli -m ggml-large-v3-turbo.bin -f clip.wav -l en -bs 8 -nt
whisper-cli -m ggml-small.en.bin        -f clip.wav -l en -bs 8 -nt
whisper-cli -m ggml-small.bin           -f clip.wav -l en -bs 8 -nt
whisper $WAV --model base.en --clip_timestamps 0,300 --output_format tsv --fp16 False
```

Decoder output is a transcript of a copyrighted recording, so it stays in the private
cache and is not committed. What is committed is this recipe, the anchors, and the
evidence — enough to check the reading, not enough to republish the episode.

A target is `verified` only where both decodes carry it and a timestamp locates it.
Where they disagreed, the manifest said so rather than picking a winner: Gray/Greg,
Kat/Cat, Gartog/Gartok/Garntak/Garth. Three of those are now settled — see
[A human ear, and a written source](#a-human-ear-and-a-written-source) below. Structure —
music boundaries, gap statistics, loudness — comes from `ffmpeg` measurement, not from any
model.

Contested passages were re-decoded by four further local models (whisper `base.en`,
ggml `small.en`, ggml `small` multilingual, and `large-v3-turbo` at beam 8). One split
is worth stating in full, because it is the clearest example of the risk this whole
section is about:

> At **00:02:08** four decodes hear "hope that nothing happens to **me** in the time
> frame" and two hear "nothing happens to **Maria**". The two readings differ by two
> syllables, so this is not a near-homophone; it is a plausible case of a model's
> contextual prior — this is the Maria Mercurial arc, and the name saturates the
> surrounding episodes — manufacturing a name that may not be spoken. It is recorded as
> unresolved. A human ear would settle it in five seconds, and none was available.

An ear became available, and it did not settle it. See below.

The surname *Mercurial* appears in **no** decode of the window, by any model; the full
name is first spoken at about 00:21:42. The negative control below is therefore stated
against the full name, which is safe, rather than against the given name, which is not.

Two targets take their spelling from outside the audio, which the manifest states on each:
**Entei** from the publisher's tags, and **nuyen** from Shadowrun's setting vocabulary.
The audio establishes that the words are spoken; it cannot establish how they are written.

This method has a cost that must travel with any score computed against this item:

> **Contamination.** Truth built with an ASR engine gives that engine an undeclared
> advantage. `large-v3-turbo` and `medium.en` must not be scored against these targets
> without stating the dependency in the result. A third engine is scored fairly on
> *content* recall — the targets are entities and events, not word strings — but even
> then, anything either reference engine mis-heard consistently is invisible to this
> truth set.

Every engine that touched this annotation is listed in the manifest's
`truth.contaminating_providers`, so a scoring run can refuse the combination instead of
depending on someone having read this paragraph. The validator requires that list once
any target is machine-assisted.

The `nuyen` target is the deliberate counter-example: both reference decodes wrote "new
yen", so the recorded truth differs from what either engine produced. Targets like it are
worth more than targets both engines got right.

## A human ear, and a written source

Added at B03. An operator listened to the excerpt and answered B02's follow-up list, and a
written source turned up that answers more of it than listening could. Four items changed;
the more useful outcome is what the exercise revealed about the questions themselves.

**Two of the four questions were unanswerable by ear, and that was our error.** Kat/Cat and
Gray/Grey are homophone pairs. No amount of listening separates them, because the
difference is orthographic and audio carries no orthography. B02 filed them next to
Gartog/Garth in one list of "decoder disagreements", which is accurate but conflates two
different kinds of question: one a listener can answer, one only a document can.

The document exists. The publisher keeps a cast page —
[Cast Of Shadows → Shadowrunners](https://www.hiddengrid.com/cast-of-shadows/shadowrunners/),
read 2026-07-26 — listing the retired player characters of this campaign:

| Cast page says | Effect |
|---|---|
| `Katherine (Kat) – Hunting her clone` | **Kat**, not Cat. The label was already right; it now rests on a source rather than a decoder's preference |
| `Brother Shango / Mr Grey – Setting up an empire` | **Grey**. B02 recorded *Gray* — **wrong**, and now corrected throughout |
| `Gartog – Working as Roadee for Maria Mercurial` | **Gartog**, settling the Gartog/Gartok pair the ear could not |
| `James – Off in Germany with a special mask`, `Pulse – In prison` | Corroborates both |

**Freya is not on that page.** That label still rests on decoder agreement alone, and is now
the only character name here with no written source behind it.

What the ear did settle: at 00:04:29 the listener hears Gray or Grey, which eliminates the
"Greg" one decoder produced; at 00:08:46 they hear "Gartog", eliminating Garth and Garntak.
Those two items are now `audio_observed`.

**The 00:02:08 report is the interesting one, and it does not say what it appears to.**
Asked about 00:02:08, the listener reported hearing *"Cat's gonna drive me"* — a sentence
neither decoder produced there. But both decoders place "Kat's going to drive me" at
**00:02:05–00:02:06**, two to three seconds earlier. The listener was answering about the
neighbouring line. So the report corroborates a line already annotated, and the me/Maria
split at 00:02:08 remains open — checked before concluding anything about the decoders,
which is what the addendum asked for and what the timestamps then justified.

The lesson is cheap to state and easy to forget: **when asking a person to adjudicate a
machine's reading, give them the span, not a point.** A timestamp accurate to the second is
not accurate enough to identify a sentence in overlapping speech.

## What a score here does and does not diagnose

It can diagnose:

- whether important entities and events in ten minutes of real, unrehearsed play are captured;
- whether recap is attributed as recalled rather than as happening now;
- whether the episode's furniture — theme music, dice mechanics, table banter — stays out of the campaign record;
- whether setting vocabulary survives, on two targets no reference engine got right;
- whether a system separates the people at the table from the characters they voice, on a case where the audio states the mapping outright;
- whether a name available only from metadata (Maria Mercurial) is asserted from audio whose decodes never contain the surname.

It cannot diagnose:

- word error rate, or anything at word level: no reference transcript exists, and building one from ASR would measure agreement with the reference engine rather than accuracy;
- diarization accuracy beyond a coarse count, for want of per-speaker channels and voice prints;
- behaviour on the product's actual target condition — a single room, a single iPad microphone, no post-production. This item is produced, gated, band-limited online play. The corpus still has no single-room tier, and this item is not a substitute for one;
- long-session behaviour: memory, resume, and drift need the multi-hour tier, not ten minutes.

A number from this item is evidence about ten minutes of one 2013 podcast episode. It is
the first real audio evidence the project has, and that is exactly as far as it goes.

## Rights finding

B01 recorded CC BY-NC-ND 4.0. The episode page's raw HTML carries `rel="license"` to
`creativecommons.org/licenses/by-nc-sa/3.0/deed.en_US` and the text "This work is licensed
under a Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported License",
checked 2026-07-26. The manifest now records **CC BY-NC-SA 3.0 Unported**.

ShareAlike, unlike NoDerivatives, would permit an attributed noncommercial derivative under
the same licence — so the constraint that shaped this goal was stricter than the source
requires. Handling does not change: redistribution stays `restricted` because the recording
embeds Shadowrun material owned by Topps, which the site's licence cannot sublicense, and
because repository policy keeps media and full transcripts out of Git regardless of licence.
The publication date was corrected the same way: the episode post is dated 2013-11-29,
while the media file's `Last-Modified` is 2014-05-24, which B01 had recorded as the
publication date.
