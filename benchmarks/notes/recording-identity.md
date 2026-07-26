# Recording identity when bytes cannot be reproduced

Goal: B04 (issue #21). Written 2026-07-26.

Tool: [`../../scripts/audio_identity.py`](../../scripts/audio_identity.py).
Tests: [`../../tests/test_audio_identity.py`](../../tests/test_audio_identity.py).
Fingerprints: [`../fingerprints/`](../fingerprints/).

This file is the demonstration behind the claim that a second person holding a different
download can establish that their copy is the recording this corpus annotated, and that the
committed offsets apply to it. The goal asked for that to be demonstrated rather than
asserted, so what follows is the actual runs and their actual output, including the two
places where the procedure was wrong before it was right.

## The problem, stated exactly

B02's guarantee was a digest. `scripts/fetch_benchmark_media.py` downloads the published
file, digests it, and refuses to proceed unless the digest matches `source.media_sha256`.
Every anchor in that manifest is an offset into *those* bytes, and the digest is what makes
the offset mean something.

That guarantee does not extend to a source that re-encodes on delivery. Two people who ask
YouTube for the same video get files that share no bytes: different container, different
codec, different bitrate, different encoder delay. A digest recorded from one download pins
nothing for anyone else. Left there, a truth item anchored at 3 h 29 m 51 s is an offset
into a file that only the annotator has ever held.

The failure is silent, which is what makes it serious. A reader whose copy begins 400 ms
earlier gets an answer at every anchor. It is just the wrong moment, and nothing in the
data says so.

## What was measured, not assumed

The premise above is a claim about this source, so it was checked rather than repeated.
Three audio streams were obtained for the same video id on 2026-07-26:

| yt-dlp format | Container | Codec | Output rate | Bitrate | Bytes | SHA-256 |
|---|---|---|---|---|---|---|
| 140 | MP4 | AAC-LC | 44100 Hz | 129380 | 230265075 | `83999e0c…af7f` |
| 251 | WebM | Opus | 48000 Hz | 110922 | 197413805 | `0d3022ba…986a` |
| 139 | MP4 | HE-AAC | 44100 Hz | 48690 | 86657091 | `fbe2350c…414e` |

Three files, three digests, one recording. Any procedure that compares bytes calls these
three different things. So the premise holds here: the digest cannot be the identity.

Format 139 is the interesting one. HE-AAC reconstructs the top of the band from parametric
side information rather than coding it, so ffprobe reports a 44100 Hz output rate over a core
running at half that, at 38% of format 140's bitrate. If a loudness envelope were going to
break anywhere among these three, it would break there.

## The answer: describe the sound, not the file

A **content fingerprint** — the RMS level per frame of the decoded audio, after a stated
normalization to mono 16 kHz. A loudness envelope: how loud the room was, second by second.

Two properties make it the right object:

- **It survives re-encoding.** Every codec above is trying to preserve the same waveform.
  They disagree about the samples and agree about the energy.
- **It is not media.** At one frame per second a four-hour recording is 14239 numbers. No
  speech, no words, and nothing identifying anyone can be recovered from it — which is what
  makes it committable under the repository's rule that recordings and transcripts do not
  enter Git.

Identity is then a correlation, and the offset is the lag at which the correlation peaks.
The reader gets both from one procedure: *is this the same recording*, and *by how much is
my copy shifted*.

### Two resolutions

The committed fingerprint carries a coarse pass and a fine pass because they answer
different questions.

- **Coarse**, one frame per second across the whole recording. Locates a copy whose lag is
  unknown and possibly large. It cannot judge identity — see the trimmed-copy row below.
- **Fine**, one frame per 10 ms over a short probe window. Measures the offset to a
  precision the anchors can actually use, and decides identity.

## Reproducing the check

```bash
uv run python scripts/audio_identity.py verify <your-audio-file> \
  --against benchmarks/fingerprints/mystic-horizon-ch1ep1-killing-zombozos.json
```

It prints a correlation, an offset, and a verdict, and exits non-zero when the copy is not
the recording. A non-zero offset is not a failure: it is the correction to apply to every
anchor in the manifest before using them.

The fingerprint itself was written with:

```bash
uv run python scripts/audio_identity.py fingerprint copy_a_fmt140.m4a \
  --out benchmarks/fingerprints/mystic-horizon-ch1ep1-killing-zombozos.json \
  --probe-start 300 --probe-seconds 60
```

## The demonstration

Five cases, chosen so that agreement and disagreement are both possible.

| Copy | Coarse *r* | Fine *r* | Offset reported | Verdict | Exit |
|---|---|---|---|---|---|
| Format 140, the reference itself | 1.0000 | 1.0000 | +0.000 s | same recording | 0 |
| Format 251, Opus 111 kbit/s | 0.9923 | 0.9931 | −0.040 s | same recording | 0 |
| Format 139, HE-AAC 49 kbit/s | 0.9809 | 0.9999 | +0.060 s | same recording | 0 |
| Format 251, re-encoded and trimmed 12.347 s | 0.7769 | 0.9989 | −12.380 s | same recording | 0 |
| `dice-and-die-lmop-e01`, an unrelated recording | 0.0456 | — | — | **different recording** | 1 |
| Mystic Horizon Ch. 1 **Ep. 2**, same cast and setup | 0.0465 | — | — | **different recording** | 1 |

Verbatim output for the four positive cases, and for the adversarial control:

```text
########## copy_b_fmt251.webm
coarse correlation: 0.9923 over 14239 frames
coarse lag: +0 s (locates the fine pass; does not judge)
fine correlation: 0.9931 over 5704 frames
offset to apply: -0.040 s
SAME RECORDING
Anchors apply as committed; the offset is below the annotation's precision.
exit=0
########## copy_c_fmt139.m4a
coarse correlation: 0.9809 over 14239 frames
coarse lag: +0 s (locates the fine pass; does not judge)
fine correlation: 0.9999 over 5694 frames
offset to apply: +0.060 s
SAME RECORDING
Add -0.060 s to committed anchors to locate them in this copy.
exit=0
########## shifted_exact.webm
coarse correlation: 0.7769 over 14214 frames
coarse lag: -12 s (locates the fine pass; does not judge)
fine correlation: 0.9989 over 5738 frames
offset to apply: -12.380 s
SAME RECORDING
Add +12.380 s to committed anchors to locate them in this copy.
exit=0
########## same_campaign_ep2.webm
coarse correlation: 0.0465 over 1469 frames
coarse lag: +32 s (locates the fine pass; does not judge)
DIFFERENT RECORDING: no alignment above 0.3 to refine
This copy does not follow the same loudness envelope. Committed anchors do
not apply to it, and no offset can make them apply.
exit=1
```

The recovered offset on the trimmed copy is worth reading closely, because it is the number
the whole exercise is for. The trim was 12.347 s; the tool reports 12.380 s. The 33 ms
residual is a real limit and not rounding: it is the sum of the fine pass's 10 ms frame and
the Opus re-encode's own delay. Anchors in this corpus are recorded to the second, so a 33 ms
correction error does not reach them — but it is the precision floor, and anyone tempted to
anchor to the syllable should know where it sits.

### Why each case is there

**The reference against itself** is a null check and claims nothing about identity — it only
shows the procedure introduces no error of its own, so the deviations in the rows below are
the encodes and not the tool.

**The two alternative encodes** are the case the goal actually asks about: a second person
downloads and gets a different file. Re-downloading format 140 and finding it matches would
have proved nothing, because that is the byte-identity case a digest already covers. These
share no bytes with the reference, and one of them is at half the sample rate and a third of
the bitrate.

**The trimmed copy** tests the offset half of the claim, which is the half that fails
silently. A copy with 12.347 s removed from the front is still the same recording, and every
committed anchor is wrong for it by exactly that much. The procedure has to say both things:
same recording, here is your correction.

**A different recording** proves the verdict is capable of coming out negative. Without it
the tool could be returning "same recording" unconditionally and every other row would look
identical.

**A different episode of the same campaign** is the case that matters most and the one it
would have been easiest not to run. Same cast, same microphones, same room tone, same game,
same channel, same encoder — everything the previous row varies is held constant, and only
the content differs. It scored 0.0465, indistinguishable from an unrelated recording. That
rules out the interpretation that would have quietly voided the whole exercise: that the
envelope is recognising the *setup* rather than the recording.

## Where the threshold came from

`SAME_RECORDING_R = 0.90` and `COARSE_PEAK_FLOOR_R = 0.30`, and neither is a guess. The
measured extremes are on the table above. On the fine pass — the one that judges — the worst
a genuine copy managed was 0.9931. On the coarse pass, the worst was 0.7769. The best either
different recording managed was 0.0465. So the gap the thresholds have to sit inside is
0.0465 to 0.7769, and both do, with an order of magnitude of room below and a wide margin
above.

`tests/test_audio_identity.py` pins that reasoning rather than the numbers, by asserting each
threshold falls inside the gap measured **on the pass it governs** — 0.0465–0.9931 for the fine
threshold, 0.0465–0.7769 for the coarse one. The two bounds differ because the same trimmed
copy scores 0.7769 coarsely and 0.9989 finely; a single band for both would be wrong in one
direction or the other, which an earlier version of that test was. Moving either threshold
outside its gap fails, which is the point: a threshold is only meaningful while the gap it was
read from still holds.

## Two ways this was wrong first

Both are recorded because a demonstration that only shows the passing run is not a
demonstration.

**The coarse pass cannot judge identity.** The exactly-trimmed copy scored 0.7769 coarsely —
a genuine copy, correctly rejected by any threshold worth setting. The cause is not subtle
once seen: coarse frames are a second long, so under a fractional-second shift every frame
averages a different slice of the sound than the reference frame it is being compared with.
At 10 ms the same misalignment is under one frame and the copy scores 0.9989. The fix was
to let the coarse pass only *locate* the lag and give the verdict to the fine pass.

**The fine search range was exactly the expected lag.** The 22 kHz copy was rejected at
0.7645. The true peak sat at lag 300 of a 300-frame search — the boundary, where a decoder
that seeks a few frames differently pushes the answer outside the range entirely. The search
now runs to twice the expected lag, leaving slack on both sides, and the same copy scores
0.9999.

There was also a third alarm that was not a defect. An early trim test appeared to show a
2.3 s error in the recovered offset. `ffmpeg -ss ... -c copy` seeks to a cluster boundary, so
the file had actually been trimmed by 10.021 s rather than the 12.345 s requested; the tool's
answer was right and the test was wrong. It is mentioned because the first instinct was to
change the tool.

### Three more found in review

None of these had produced a wrong answer yet, which is what makes them worth recording.

**A lag was called `lag_seconds` and held frames.** True only because the coarse pass uses
one-second frames. The fine pass has always been in units of 10 ms, and the coarse search
range was `int(MAX_PLAUSIBLE_LAG_SECONDS)` — a frame count being handed a number of seconds.
A fingerprint written at 500 ms would have searched 30 s instead of 60 and reported genuine
copies beyond that as different recordings. Every frame size now comes from the fingerprint,
the field is `lag_frames`, converting is the caller's job, and the fine pass returns an
`Offset` in seconds so the two cannot be confused. A test builds a 500 ms fingerprint with a
40 s lag and fails against the old arithmetic.

**The validator took a declared fingerprint on trust.** It checked that the field was present
and shaped correctly, which establishes nothing: a typoed path or a digest that stopped
matching left a manifest passing validation with anchors no reader could use — the exact
failure the field exists to close. Unlike `media_sha256`, this digest *is* checkable here,
because the file it names is committed in this repository. The validator now opens it and
hashes it.

**The fingerprint file carried the threshold, and it was stale.** It recorded
`same_recording_correlation: 0.98` from before the threshold was settled at 0.90, while
nothing ever read the field. The field is gone rather than corrected: a threshold belongs to
the tool, and a copy of it in the data can only drift. The fingerprint was regenerated, which
changed its digest — recorded in four places and, at that point, checked in one. The manifest's
copy is the validator's business. The three transcript windows each carry their own and nothing
looked at them, so `tests/test_benchmark_transcripts.py` now does, along with the declaration
in those files that they are not a reference. Both mutations were confirmed to fail.

## What this does and does not establish

It establishes that a reader with an independently obtained copy can determine whether it is
this recording, and can recover the offset to apply to the committed anchors. That is what
the goal asked for.

It does not establish anything about a copy that has been edited rather than re-encoded or
trimmed. A copy with a section removed from the middle will align on one side of the cut and
not the other; the coarse correlation would fall, and the honest reading of a mid-range
coarse score is "something has been changed", not "close enough". Nothing in the corpus
currently needs that case, and if one arrives it needs its own demonstration rather than an
extension of this one by assumption.

It also assumes the reader can decode their copy with ffmpeg. That is the same dependency
the acoustic measurements already carry.

## Reuse

`benchmarks/notes/` is the right place for a second annotator to start. The procedure is not
specific to this recording: the other admitted item, `dice-and-die-lmop-e01-stranger-danger`,
is CC BY 3.0 from the same platform and has the same problem. Fingerprinting it is one
command, and the schema field it needs — `source.content_fingerprint` — is already there.

The validator enforces the connection rather than trusting a note: a manifest with a verified
target and neither `source.media_sha256` nor `source.content_fingerprint` fails, on the
grounds that an anchor into bytes nobody can confirm is not evidence.
