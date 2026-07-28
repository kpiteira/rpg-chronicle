# Product boundaries

## Owned from the beginning

- Session lifecycle and resumability
- Canonical transcript/session representation
- Campaign vocabulary and correction history
- Review prioritization and attention budget
- Hierarchical RPG analysis
- Physical-speaker versus fictional-character model
- Evidence and confidence handling
- Campaign-change package
- Export adapter contracts

## Initially borrowed

- Audio conversion
- Voice activity detection
- Speech recognition
- Word alignment
- Speaker diarization
- Speaker embeddings
- Local model serving
- Audio playback components

## Evolution rule

External components are processors, not sources of truth. Normalize their output immediately and retain engine-native artifacts for debugging. Replace a component only when benchmarks show it limits product outcomes.

## What the canonical boundary carries

The canonical session is deliberately narrow (D-006) and grows only on consumer evidence.
It is at schema `0.2`. A `TranscriptTurn` carries the text and, where a producer measured
them, three qualities of the turn rather than of the words: what quantity its `confidence`
is (`confidence_kind`), and how much of the turn its speaker label covers
(`speaker_coverage`, `speaker_purity`). A `CanonicalSession` carries `entities` with their
aliases and open `threads`, both as evidence-bearing claims.

The rule that decides whether something belongs here is not "would a consumer like it".
It is: **can a consumer that reads only canonical turns act correctly without it?** Every
field above failed that test with a named consumer and a measurement behind it (D-018).
The engine-native artifact keeps its copy of each — it is the debugging record — but it is
no longer the only copy, because a consumer bound by D-006 cannot read it.
