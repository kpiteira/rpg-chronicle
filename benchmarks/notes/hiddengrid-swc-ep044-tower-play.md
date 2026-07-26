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

Two consequences worth carrying forward. The single mixed track means **there is no
per-speaker channel**: any diarization probed here works from one signal, as it would on
the target iPad recording. And the gated near-silence between utterances, together with
post-production levelling and limiting, means this is a **produced** artifact — it is not
the raw acoustic condition the product is aimed at, and it should not be read as a proxy
for one.

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

Seven distinct first-person role-holders speak in the window: the game master, and the
players of Kat, Pulse, James, Gray, Freya and Gartog. Adjacent-turn exchanges prove at
least five are different people — Kat and Pulse argue at 00:02:35, Kat and James hold a
phone call at 00:04:04, James and Gray speak in the same room at 00:04:10, Freya and the
game master trade jokes at 00:05:51. No voice-print separation was performed, so one
person voicing two of the seven roles is not excluded. **Score against 7 as
"role-holders heard" and 5 as the proven floor.**

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

A target is `verified` only where both decodes carry it and a timestamp locates it.
Where they disagree, the manifest says so rather than picking a winner: Gray/Greg,
Kat/Cat, Gartog/Gartok/Garntak/Garth. Structure — music boundaries, gap statistics,
loudness — comes from `ffmpeg` measurement, not from any model.

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

The `nuyen` target is the deliberate counter-example: both reference decodes wrote "new
yen", so the recorded truth differs from what either engine produced. Targets like it are
worth more than targets both engines got right.

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
