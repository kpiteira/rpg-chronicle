# Content fingerprints

A fingerprint here answers a question a checksum cannot: **is the copy in front of you the
recording this corpus annotated, and where does it start?**

`scripts/fetch_benchmark_media.py` verifies a source by digesting its bytes. That works for
a file served as a file. It does not work for a source that re-encodes on delivery: two
people who download the same video get files that share no bytes, so a digest pins nothing,
and a truth item anchored at 2 h 41 m 03 s could be pointing anywhere in a reader's copy.

The fingerprint describes the *sound* instead. It is the RMS level per frame of the decoded
audio, after a stated normalization to mono 16 kHz — a loudness envelope. Re-encoding barely
moves it; a different recording does not follow it at all.

```bash
# Check a copy you obtained yourself
uv run python scripts/audio_identity.py verify <your-audio-file> \
  --against benchmarks/fingerprints/<manifest-id>.json
```

It prints a correlation, an offset, and a verdict, and exits non-zero when the copy is not
the recording. If the offset is non-zero, apply it to every anchor in that manifest before
using them.

## What is in the file

Two resolutions, because they answer different questions:

- **coarse**, one frame per second across the whole recording, which locates the copy's lag even when it is far off;
- **fine**, one frame per 10 ms over a short probe window, which measures the offset closely enough for millisecond anchors and decides identity.

Identity is decided on the fine pass. The coarse pass only points at where to look — a
genuine copy trimmed by a fractional second scores 0.78 coarsely, because second-long frames
straddle different slices of the sound once shifted, and it scores above 0.99 finely.

## Does it work?

[`../notes/recording-identity.md`](../notes/recording-identity.md) is the demonstration:
three genuinely different encodes of one recording, a copy trimmed by 12.347 s, an unrelated
recording, and — the control that matters — a different episode of the *same campaign*, with
the same cast, room and encoder, which the procedure rejects at 0.0465. It also records every
way the procedure was wrong before it was right, which by now is more places than it is
comfortable to list here.

## These are measurements, not media

A loudness envelope is a few thousand numbers describing how loud the room was. No speech,
no words, and nothing identifying anyone can be recovered from it. It is committed for the
same reason the acoustic measurements are: so a reader can check a claim without repeating
an acquisition that may not return the same bytes.

## Attribution

The fingerprints are derived from recordings under Creative Commons Attribution 3.0, which
permits derivative works with attribution. Attribution for each:

- `mystic-horizon-ch1ep1-killing-zombozos.json` — derived from *D&D: Mystic Horizon | Ch. 1 Ep. 1 | Killing Zombozos* by **SIR HORSE**, <https://www.youtube.com/watch?v=-ZzSFGgczrI>, licensed [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/). Licence read from the watch page markup on 2026-07-26. Modified: reduced to a per-frame loudness envelope.
