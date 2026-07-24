# Current project status

Last updated: 2026-07-24

## Current outcome

The repository has a verified synthetic R0 skeleton:

```text
fixture processor output
→ canonical transcript turns
→ fixture-backed scene/session analysis
→ evidence-backed summary-first review package
```

The path is resumable, preserves the processor-native artifact, and passes two tests
plus lint. It is scaffolding for parallel discovery, not evidence that a real audio or
analysis engine has been selected.

## Active milestone

`M0 — Team-ready bootstrap`, immediately feeding `M1 — R0 public vertical slice`.

## Accepted facts

- No specialist branch or durable specialist finding has been integrated yet.
- No public benchmark excerpt or provisional real transcription engine is selected.
- The canonical schema is version `0.1` and intentionally narrow.
- The existing analysis is declared fixture truth, not generated model output.
- The external reference vault must remain read-only during discovery.
- The initial bootstrap establishes the shared product, operating, and executable
  foundation; agents must preserve it and never assume unfamiliar files are disposable.
- The bootstrap installer excludes Git metadata and local caches and never overwrites
  files already present in a target checkout.

## Parallel focus

| Role | Start item | Integration dependency |
|---|---|---|
| Reuse research | `R01` component scorecard | Needs benchmark criteria; can begin from documented evaluation dimensions |
| Benchmark research | `B01` manifest schema and candidates | Independent; unblocks public-source convergence |
| Review and analysis | `A01` analysis/review contract | Uses the existing synthetic canonical fixture |
| Vault discovery | `V01` sanitized vault-structure report | Requires configured external path; falls back to contract work if unavailable |

## Integration focus

The next convergence point is `I01`: replace the source-specific fixture path with one
public excerpt and provisional processor while retaining the canonical/review boundary.
Integration must wait for evidence from at least `B01`, `R01`, and `A01`, but the lead
can refine adapters and validation without selecting those outputs prematurely.

## Known blockers

- GitHub issues, assignments, and milestones have not yet been seeded from the
  bootstrap backlog, so `docs/BACKLOG.md` remains the authoritative work queue.
- Vault discovery may lack a configured private path. This does not block `V02`,
  the vault-neutral campaign-change contract and safety policy.
