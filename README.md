# RPG Chronicle

Local-first software for turning long tabletop RPG recordings into attributed transcripts, trustworthy session summaries, structured campaign knowledge, and eventually safe Obsidian vault updates.

## North star

After a game, the recording is processed automatically. The user reviews a concise summary, answers only a handful of high-value questions, previews campaign changes, and approves them in roughly five minutes.

## Strategy

Start with reusable transcription, diarization, and local-LLM components behind stable interfaces. Replace components only when measured evidence shows that ownership improves quality, privacy, reliability, or human attention.

## Repository boundary

This public repository contains reusable software, documentation, benchmark manifests, synthetic fixtures, and reproducible research results.

It must not contain private campaign data, voice profiles, downloaded copyrighted audio, session recordings, private vault contents, or secrets. Runtime data may live anywhere on local disks or a NAS and is referenced through configuration.

## Start

1. Read `AGENTS.md`.
2. Read `docs/PRODUCT.md` and `docs/EXECUTION.md`.
3. Select a role from `agents/`.
4. Read `docs/PARALLEL_EXECUTION.md` if you are running more than one role at once.
5. Copy `config/paths.example.yaml` to a local ignored location and point it at external data.

For parallel role sessions, the complete bootstrap prompt is:

```text
You are the <role> agent.
/goal <the role's condition from docs/PARALLEL_EXECUTION.md>
```

The first line selects the role, which the repository routes through inherited
instructions and durable shared context. The second sets the native goal condition
that drives the session. Specialists resolve their single active GitHub goal and
own execution through Copilot-reviewed GitHub merge. See `docs/OPERATING_MODEL.md`,
`docs/GOALS.md`, `docs/MILESTONES.md`, and `CONTRIBUTING.md`.

## First milestone

`audio → transcript → speaker turns → scene analysis → session summary → targeted review package`

## Run the synthetic vertical slice

The first executable path uses a synthetic engine-output fixture, so it requires no private
audio or model download:

```bash
python -m rpg_chronicle.cli run-fixture \
  benchmarks/fixtures/r0_synthetic_session.json \
  --output /tmp/rpg-chronicle-demo
```

The command writes a resumable canonical session, preserves the processor-native artifact,
and produces `review-package.json` with a targeted attention queue.

The analysis in this slice is **declared fixture truth replayed through the
`AnalysisProvider` interface**, not model output. Every artifact records this in its
`provenance` block. The slice demonstrates that the stage boundaries, evidence handling,
and resumability work; it demonstrates nothing about analysis quality.
