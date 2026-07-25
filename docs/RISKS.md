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
| Active goals become ambiguous or duplicate | High | Exactly one `agent:*` and `goal:active` issue per specialist; `/goal` fails closed on zero or multiple matches |
| Autonomous PRs drift across architecture boundaries | High | Goal constraints, canonical contracts, Copilot review, decision records, and TPM outcome-level architecture assessment |
| Review automation is mistaken for approval | Medium | Specialists must wait, triage every comment critically, rerun checks, and verify mergeability before GitHub merge |
| Tests that assert declared fixture truth are mistaken for capability | Critical | Provider-agnostic invariant tests, provenance recorded in every artifact, validator tautology check, benchmarks never report fixture-provider output |
| Implementing agent judges its own goal satisfaction | High | Fresh-context goal validator, fail-closed `PreToolUse` merge gate bound to the PR head commit, verdict recorded on the PR; branch protection on `main` is the layer outside the implementer's identity |
| Capture quality caps every downstream result | High | Permanent table microphone, one-time speaker enrollment, benchmark tier comparing iPad-only against table-mic audio for the same session |
| Schedule pressure converts into unverified merges | High | August 11 scoped to R1, vault writes deferred, merge gate independent of the deadline |
| Parallel specialists collide on shared files | Medium | Declared file ownership in `docs/PARALLEL_EXECUTION.md`, TPM-owned canonical model, small frequent merges, branch-currency check in CI |
