# Evaluation strategy

## What matters most

The decisive metric is useful, trustworthy campaign knowledge per minute of human attention. Word error rate is informative but not sufficient.

## Corpus tiers

1. Polished professional actual play
2. Amateur online sessions
3. Single-room, single-microphone sessions
4. Controlled or synthetic clips with known truth
5. A multi-hour stress case

## Repository policy

Commit the software and the decisions about it: scripts, schemas, small synthetic
fixtures, research findings, and aggregate results.

**Do not commit content.** Recordings, transcripts, per-recording manifests, answer keys and
annotation notes live in the content directory beside the audio — `~/.rpg-chronicle` by
default, `RPG_CHRONICLE_HOME` to override. This does not depend on a licence: a licence
answers whether we may publish something and never whether we should, and an answer key is
in any case meaningless away from the recording it answers for. `docs/CONTENT_AUDIT.md`
records the audit that established this, file by file.

The one exception is content that is **synthetic and executed**: invented sessions under
`benchmarks/fixtures/` are test inputs, `uv run pytest` fails without them, and nobody's
speech is in them.

## Evaluation dimensions

- Major plot events captured
- Important people, places, factions, items, and quests captured
- Unsupported important claims
- Speaker attribution quality
- Fantasy-name accuracy
- Processing time and memory
- Resume and recovery behavior
- Review question count
- Human review time
- Important errors not surfaced

## First benchmark set

Start small:

- Two polished excerpts
- Two amateur online excerpts
- Two single-room excerpts
- One longer session
- One intentionally degraded sample

Create careful reference annotations only for short, representative sections and important entities/events.

## Annotation provenance

Truth is only worth what its provenance says it is, so every annotated item records how it was made.

- A target is `verified` only when it was observed in the recording, anchored to a time inside the excerpt window. A target taken from a title, description, or index stays `provisional` no matter how confident it looks.
- Observation by ear (`audio_observed`) and observation through tooling (`audio_machine_assisted`) are both verifiable and are recorded as different things. Folding them together would let machine-read truth pass as heard truth in the one field a consumer is most likely to read alone.
- `truth.method` names the procedure and any provider whose output contributed. `scripts/validate_benchmark_manifests.py` refuses a manifest that verifies a target without it.
- Machine-assisted annotation is legitimate and must be declared. An engine that helped build the truth cannot be scored against it without stating the dependency in the result, because it is being marked against its own output. `truth.contaminating_providers` names those engines in the manifest so a scoring run can check the combination rather than trusting that someone read the notes.
- A field a consumer reads alone must not carry an inference. Where part of a claim is measured and part is inferred — capture layout is the usual case — the field states the measured part and the inference goes in `observations` with its evidence.
- Where decoders disagree and no human ear settled it, record the disagreement rather than a winner. An unresolved item is information; a guessed one is not.

Annotated items and their per-item notes live in the content directory under
`benchmarks/`. Read an item's note before reporting any number against it.

Provenance is checked by `scripts/validate_benchmark_manifests.py`, which the operator runs
against that directory — `~/.rpg-chronicle/benchmarks/manifests` by default, or a directory
named as its first argument, with `--content-root` when that directory is not laid out as
`<root>/benchmarks/manifests`. It is no longer a CI step: CI has no content directory, and
giving it one would mean committing what the policy above keeps out. That is a real reduction in
automated enforcement and the price of the split — `research/what-real-recordings-do.md`
holds the findings that survived it.
