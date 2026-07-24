# Initial risk register

| Risk | Impact | Initial mitigation |
|---|---|---|
| Single iPad microphone produces weak distant speech | High | Preserve original audio, detect poor sections, benchmark degraded/table recordings, support targeted retranscription |
| Overlapping speech breaks diarization | High | Treat diarization as optional enrichment, preserve anonymous fallback, use confidence and short review samples |
| Fantasy names are corrupted | High | Campaign vocabulary, multi-engine disagreement, repeated-term detection, summary-first corrections |
| Review burden becomes too high | Critical | Attention budget, importance ranking, bundled corrections, measure review time from the first prototype |
| Long jobs fail or restart from zero | High | Resumable stages, immutable source audio, cached artifacts, partial-result preservation |
| Existing component creates lock-in | Medium | Stable provider interfaces and canonical internal model |
| Vault updates overwrite authored work | Critical | Change preview, explicit ownership rules, provenance, rollback, no silent destructive updates |
| Public repo leaks private/copyrighted material | Critical | External paths, strong ignore rules, sanitized fixtures, review before commits |
