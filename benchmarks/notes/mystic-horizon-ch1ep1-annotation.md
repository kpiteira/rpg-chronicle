# Annotation record: Mystic Horizon Ch. 1 Ep. 1, full 3 h 57 m

Manifest: [`../manifests/mystic-horizon-ch1ep1-killing-zombozos.json`](../manifests/mystic-horizon-ch1ep1-killing-zombozos.json)
Annotated: 2026-07-26. Goal: B04 (issue #21).

Identity procedure: [`recording-identity.md`](recording-identity.md). Read that first if you
are checking these anchors against your own copy — they are offsets into a recording, and
this source does not serve the same bytes twice.

No audio and no full transcript of this episode is in the repository. Short quotations
needed to anchor a target appear here and in the manifest, attributed. The window
transcripts under [`../transcripts/`](../transcripts/) are a separate, licence-checked
artefact with their own caveats; they are drafts, not a reference, and they say so.

## What this item is for

Every other item in the corpus is minutes long. This one is 3 h 57 m 18 s in a single
continuous live stream, which is the only way to exercise the failure the product actually
has to survive: a thread opened in the first ten minutes and paid off in the last ten,
across four hours of intervening play that a system has to hold or discard correctly.

So the annotation is deliberately lopsided. The **thread and entity layer spans the whole
recording**; the **transcript windows do not**. Nine minutes are transcribed out of 237.
`docs/EVALUATION.md` asks for exactly that shape, and the issue made it a constraint,
because four hours of correction is unbounded work and windows are the control.

## How the recording was decoded

| Pass | Engine | Scope |
|---|---|---|
| Primary | whisper.cpp `large-v3-turbo`, beam 5, Metal | the full 3 h 57 m |
| Secondary | openai-whisper `medium.en`, CPU | every anchor window, plus the three transcript windows and one diagnostic block |

Different implementations and different model families, both run locally on a private copy,
as in the Hiddengrid item. A target is `verified` only where both engines carry it. Where
they disagree, the disagreement is in the evidence rather than resolved by preference.

Both engines are named in `truth.contaminating_providers`. Neither can be scored against
this item without declaring the dependency.

Nothing here was heard by a person. Every target's basis is `audio_machine_assisted`, and
`proven_distinct_speakers` stays `null` — see below for why that is not laziness.

## Structure, measured

All figures are per-second RMS from the same loudness envelope committed as the content
fingerprint, so anyone can re-derive them from
[`../fingerprints/mystic-horizon-ch1ep1-killing-zombozos.json`](../fingerprints/mystic-horizon-ch1ep1-killing-zombozos.json)
without the audio. "ASR coverage" is the share of seconds falling inside some primary-pass
segment.

| Span | Median RMS | Loud (>−22 dB) | Quiet (<−45 dB) | ASR coverage |
|---|---|---|---|---|
| Whole recording | −25.6 dB | 30.7% | 12.7% | 85.8% |
| First hour | −25.3 dB | 32.9% | 13.4% | 85.7% |
| Final hour | −26.7 dB | 23.7% | 13.3% | 86.9% |

The recording is remarkably even. There is no ramp, no act structure, no post-production
levelling — the session simply runs, and the final hour is 1.4 dB quieter and a third less
loud than the first, which is fatigue rather than editing.

### 14% of the timeline yields no words, and none of it is silence

This is the property that makes the item worth its length, and it took two measurements to
establish rather than assume.

`silencedetect` at −40 dB with a 1.5 s minimum finds **no silent run anywhere in 3 h 57 m**.
Not one. Drop the minimum to 0.5 s and there are 3285, about 14 a minute. So the recording is
densely gapped at the scale of a breath and never quiet at the scale of a pause: an open
channel with continuous room tone.

Against that, 14.2% of seconds fall outside every primary-pass segment. The obvious reading —
the decoder dropped speech — was checked rather than assumed. `medium.en` was run
independently over 00:39:00–00:44:00, the recording's worst-covered five minutes:

| | Coverage of that block |
|---|---|
| whisper.cpp `large-v3-turbo` | 76.3% |
| openai-whisper `medium.en` | 72.3% |

The second engine covers **less**, not more, and the 19 seconds it covers that the first does
not contain, in full: "I", "You", "Um". Two independent engines agree that the uncovered
timeline carries no transcribable speech. It is laughter, dice, breath, typing, and the room —
which is what an unedited four-hour amateur stream is mostly made of.

That matters for anyone reporting a number here. A system that transcribes this recording is
being asked to stay coherent across roughly 34 minutes of non-speech distributed in 694 gaps,
and a transcription cost measured against wall-clock duration will look far worse than one
measured against speech.

## Why these three windows

Windows were chosen on the measurements above and on nothing else. Three, at three
measurably different conditions, three minutes each.

| Window | Span | Median RMS | Loud | Quiet | ASR coverage | Chosen as |
|---|---|---|---|---|---|---|
| W1 | 00:01:00–00:04:00 | −23.1 dB | 41.7% | 5.0% | **95.6%** | best case |
| W2 | 00:40:00–00:43:00 | −24.4 dB | 36.1% | 22.8% | **74.4%** | worst case |
| W3 | 03:49:00–03:52:00 | −28.7 dB | 9.4% | 18.9% | 76.1% | late and quiet |

**W1 is the recording at its most favourable.** 95.6% coverage against 85.8% overall, the
lowest quiet fraction anywhere, and the speakers are fresh. If a transcript is going to be
right anywhere in this file it is here, so a poor result in W1 is a hard result: nothing about
the audio excuses it.

**W2 sits inside the recording's worst-covered five minutes.** Its quiet fraction is more than
four times W1's, and both engines lose a quarter of the timeline in it. It is the same room
and the same people as W1, which is what makes the pair a controlled comparison rather than
two unrelated samples.

**W3 is nearly four hours in, and it is the quietest of the three by 4 dB** — 9.4% of seconds
above −22 dB against W1's 41.7%. It is also where both long threads close. A system that has
kept its early material has everything it needs here; a system that has not will produce
fluent, wrong summary, and this window is where that becomes visible.

W1 and W3 also bracket the thread layer, which is why they were preferred over any window
chosen purely on loudness.

## Threads across the full duration

The goal requires at least one recorded thread spanning more than two hours between its first
and last anchor. Two do.

| Thread | First anchor | Last anchor | Span |
|---|---|---|---|
| The soul economy | 00:09:32 | 03:51:34 | **3 h 42 m 02 s** |
| Reaper, a player addressed by name | 00:02:42 | 03:51:34 | **3 h 48 m 53 s** |
| Scarlet dies, is revived, and it is explained an hour later | 00:36:37 | 03:17:28 | **2 h 40 m 51 s** |

They are in `truth.threads`, and the validator enforces what makes them threads rather than
word counts: **each end has to be the anchor of a truth target in the same manifest.** A thread
whose end is one millisecond off a real anchor is rejected, because that number still lands in
the window and still looks like a citation with nothing at it. Three mutation tests hold that.

The one worth reading closely is the middle one:

> Scarlet is addressed by name at **00:36:37** during a scouting turn. She dies at **02:06:52**
> — "wait, are you actually dead dead", answered with "he's dead" — and the table spends the
> next three minutes looking up resurrection. **The revival is never narrated.** It is
> established at **03:17:28**, in a conversation between two characters about something else
> entirely: *"it's tough to explain, but you saw what the hand axe did with Scarlet, right,
> when I revived her."*

That sentence is the item's whole argument. A system that dropped the death an hour and ten
minutes earlier does not merely miss a fact — it cannot parse the exchange that closes the
session, because the exchange assumes it. Nothing in a ten-minute excerpt can pose that, and
nothing in the corpus could pose it before now.

Two smaller things in the same passage are worth knowing before scoring anything against it.
The table says **"he"** about Scarlet throughout the death, so a system inferring character
gender from this audio will get it wrong. And the closing recap at 03:51:37 says **"Sammy did
die"** — the player's name, not the character's — unprompted, which is how this table actually
refers to the event.

### The Reaper thread is the cheap one, and it is the one to watch

Nothing about it is dramatic. The same human being is addressed by the same short form in the
third minute and in the last, while his *character* is addressed by a different name in
between. It is exactly the kind of continuity that survives nothing and that no summary has a
reason to keep, which is why it is recorded.

## The cast, and one name nobody wrote down

The publisher's description credits five people, each with a character. That is metadata, and
under this goal's acceptance evidence an item that could have been written from the description
is not evidence at all. So the description was used for exactly one thing — **how a name is
spelled** — and never to establish that anyone is in the recording. Every target is anchored to
a moment both engines carry.

| Credited | Character | Heard as | Spelling settled by |
|---|---|---|---|
| WOLFVAME (GM) | — | "wolf" | not claimed as a target |
| Sir Horse | Honse | "Hans", both engines | the description |
| ReaperSect | Wrugmil | "rug mill" / "rug me" / "rug meal" | the description |
| Sammy Stuffies | Scarlet | "scarlet" / "Scarlett" | the description |
| Lizzie | Opal | "opal", both engines | agreed by both engines |
| — | — | **"yucky", both engines** | **nothing** |

Two of those rows are the interesting ones.

**Wrugmil is what fantasy names do to ASR.** Two engines, one sound, three different strings
between them, and not one of them is the publisher's spelling. No amount of decoder agreement
would have produced it. The audio establishes that a name of that shape is spoken and that it
belongs to someone distinct from Yucky — the game master corrects himself between the two in
one breath at 00:36:42 — and a document does the rest.

**Yucky has no written source at all.** Twenty occurrences across 3 h 02 m, addressed directly
by the game master, called twice in a row at 03:03:50 waiting for an answer, referred to as
"he", present in combat. And not in the credits. Both readings fit what is audible: a nickname
for one of the credited five, or a sixth participant the credit line omits. This is precisely
the position `Freya` is in on the Hiddengrid item, and it is recorded the same way — as a
verified target whose *spelling* rests on nothing, with the ambiguity in its evidence rather
than resolved by preference.

There is also a negative control the credits hand over for free. **Opal is credited and absent.**
The audio says so twenty seconds in: "so Opal is technically AFK, she said she'll catch up with
you guys." Any account of this session that has her acting is drawing on the credit line rather
than on the recording, and can be scored as such.

## The measurement that predicted the wrong thing

Windows were chosen on acoustics. Then the second engine was run over all three, and the
ordering came out backwards.

| Window | Chosen as | ASR coverage | Speech rate | **Cross-engine agreement** |
|---|---|---|---|---|
| W1 | best case | 95.6% | 146 wpm | **0.616** |
| W2 | worst case | 74.4% | 125 wpm | 0.753 |
| W3 | late and quiet | 76.1% | 122 wpm | **0.868** |

Agreement here is the share of the primary engine's words that survive a token-level alignment
against the second engine's, computed over the whole window so that differing segmentation does
not read as disagreement.

**The window with the best audio produced the least agreement, and the quiet one produced the
most.** Loudness and coverage did not merely fail to predict reliability, they anti-predicted
it. What tracks it in these three is speech rate — W1 is the fastest, and it is the opening
scene with everyone talking over each other, while W3 is the wind-down with one person speaking
at a time.

That is three points, so it is a hypothesis and not a law, and it is recorded because it would
have been easy not to look. The practical consequence for whoever chooses the next item's
windows: **overlap, not level, is what to measure.** Choosing on level alone found the hardest
window by accident and labelled it the easiest.

One more thing follows from the numbers. Across the three windows 87%, 87% and 93% of the second
engine's words are found in the first engine's, while the first produces up to 41% more words
than the second (437 against 309 in W1). The disagreement is overwhelmingly **omission, not
contradiction** — `medium.en` hears less, rather than hearing differently. So two-engine agreement is a weaker check than it
sounds: it catches one engine inventing a word, and it does nothing about both engines
mishearing the same way, which `Wrugmil` shows they do.

## Why `proven_distinct_speakers` is still null

The field is a floor: how many speakers are *demonstrably* different people. It stays `null`
here, and the reason is not that the work was skipped.

There are two ways to raise it. One is a person listening and reporting that these two voices
are different people; nobody has listened, so that route is closed. The other is speaker
diarization — and running a diarizer to establish this item's truth would make the item
useless for the thing it is best placed to measure. `truth.contaminating_providers` exists
precisely so a provider that helped build the truth cannot be scored against it. Buying a
number for one field at the cost of the corpus's only long-form diarization target is a bad
trade, and it would be an invisible one once the number was written down.

`expected_physical_speakers` is the upper reading and is discussed above. The honest summary
is that this recording tells you between two and six people are present and does not narrow it
further without either an ear or a tool the item must stay clean of.

## What a score here does and does not diagnose

It can diagnose:

- whether a thread introduced in the first ten minutes survives to be recognised in the last
  ten, which no other item in the corpus can pose at all;
- whether an entity established once early is still held after four hours;
- whether a summary of a four-hour session reads as one session or as four disconnected ones;
- cost and throughput at the product's real target duration, on a file with an unusual amount
  of non-speech;
- level handling on unpolished audio: 17.1 LU range, true peak +0.7 dBFS, no post-production.

It cannot diagnose:

- word error rate. The window transcripts are uncorrected machine drafts and say so in their
  own `status` field. Scoring against them measures agreement with `large-v3-turbo`, not
  accuracy;
- diarization accuracy, for want of both per-speaker channels and any established speaker
  count;
- anything about a single room with a single microphone. This is a mixed remote stream, and
  that tier of the corpus is still empty;
- behaviour on polished audio, which is what the Critical Role item is for.

## Rights, checked again rather than inherited

The goal required the licence be read from source markup rather than inherited from B03, and
it was, on 2026-07-26. The watch page carries the Creative Commons row; `yt-dlp` independently
reports `license = "Creative Commons Attribution license (reuse allowed)"` for this video id;
`lengthSeconds` is 14238 and `publishDate` 2024-07-23, both matching the manifest.

CC BY 3.0 permits attributed redistribution of derivatives, which is what makes the window
transcripts and the loudness fingerprint committable at all. Their attribution is in
[`../transcripts/README.md`](../transcripts/README.md) and
[`../fingerprints/README.md`](../fingerprints/README.md).

Two limits carry forward unchanged from B03. The uploader can only license what the uploader
owns, so Dungeons & Dragons material remains Wizards of the Coast's. And the content licence
is what grants reuse; obtaining the file from a platform is separately subject to that
platform's terms.
