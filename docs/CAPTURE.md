# Capture policy

Capture quality sets a ceiling that no downstream model choice can raise. This document
records what the project asks of the table, and why each ask is small.

## Consent

Everyone at the table is told, before the first recording, that the session is recorded
and processed. This is a standing agreement, re-confirmed when a new player joins.

- Recordings, transcripts, and voice profiles stay on local disks or a NAS.
- Audio is never uploaded to a hosted service without an explicit, per-session decision.
- Any player may ask for a session, or their enrollment sample, to be deleted; deletion
  removes the audio, the derived transcript turns, and the voice profile.
- The public repository never contains recordings, transcripts, voice profiles, or
  campaign content. See `docs/PRODUCT.md` and the repository boundary in `README.md`.

## Microphone

The product constraint is *no per-session ritual*, not *no hardware*. A one-time purchase
that is left on the table permanently costs the players nothing per session.

- **Baseline:** a single iPad placed near the table. This must keep working, because it
  is the fallback and the worst realistic case.
- **Recommended:** one omnidirectional USB or Bluetooth conference microphone placed at
  the centre of the table, always present, switched on with the recording.

A table mic typically moves word error rate more than swapping speech engines. Benchmark
tier 3 should therefore contain both an iPad-only and a table-mic recording of the same
session so the gap is measured rather than argued about.

## Speaker enrollment

Unsupervised diarization has to discover how many speakers exist and cluster them from a
noisy room. For a stable group of four to six people, that work is unnecessary.

- Each player records roughly thirty seconds of speech once, ever.
- Enrollment produces a speaker embedding stored outside the repository.
- Attribution becomes identification against a small known set rather than clustering,
  which is substantially more accurate and yields real names instead of `speaker-2`.
- Diarization remains the fallback for guests and unenrolled voices.

Enrollment is a per-player one-time cost, not a per-session ritual, so it is consistent
with the product constraint.

## What stays out of scope

- Per-player headsets or lapel microphones.
- Any capture step that must be performed correctly at the start of each session.
- Live transcription during play.
