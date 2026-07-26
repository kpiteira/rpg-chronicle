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

Commit source URLs, timestamps, licenses, manifests, scripts, small synthetic fixtures, annotations, and aggregate results. Do not commit downloaded YouTube audio unless redistribution is explicitly permitted.

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
- `truth.method` names the procedure and any provider whose output contributed. `scripts/validate_benchmark_manifests.py` refuses a manifest that verifies a target without it.
- Machine-assisted annotation is legitimate and must be declared. An engine that helped build the truth cannot be scored against it without stating the dependency in the result, because it is being marked against its own output.
- Where decoders disagree and no human ear settled it, record the disagreement rather than a winner. An unresolved item is information; a guessed one is not.

The first annotated item is `benchmarks/manifests/hiddengrid-swc-ep044-tower-play.json`, whose limits are written up in `benchmarks/notes/hiddengrid-swc-ep044-tower-play.md`. Read a per-item note before reporting any number against it.
