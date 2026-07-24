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
