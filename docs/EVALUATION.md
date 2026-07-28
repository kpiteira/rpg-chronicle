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

## The scoring harness

`rpg-chronicle score` reads a completed run and an answer key and reports the dimensions
`docs/MILESTONES.md` makes M2 conditional on. It never improves a score and never touches
the pipeline: a component that both measures and tunes cannot be trusted about either.

```bash
uv run rpg-chronicle score \
  --session <output>/<session-id> \
  --manifest <manifest-id or path> \
  --run-report <the json run-audio --run-report wrote> \
  --report <where to write the full json>
```

`--manifest` takes a bare id and finds it in the content directory, or a path. The suite
runs against `benchmarks/fixtures/scoring/`, which is invented material with nobody's
speech in it, so no content directory is needed to test the harness — only to score a real
recording. The command exits 2 when it withholds the score.

### What each dimension is, and what it is not

Two rules shape the whole report. *A number with no stated basis is worse than no number*,
so every dimension prints what it was computed from and what it does not mean, and the JSON
carries the same fields. *Partial coverage stated plainly beats seven numbers of mixed
integrity*, so a dimension that cannot be computed says so and names the missing input
rather than reporting a zero.

| Dimension | What is measured | What the number is not |
|---|---|---|
| `entity_capture` | Two bounds. `recall_by_name` is the share of annotated entity targets whose label matches an entity name or alias as whole tokens, in either containment direction. `recall_anchor_corroborated` additionally requires the entity to cite turns spanning the annotated moment. | Not a statement that the entity was described correctly. The upper bound says the name appeared somewhere; the lower bound says it appeared where the annotator heard it. The truth is between, and nothing here narrows it. |
| `plot_capture` | `coverage_upper_bound`: the share of anchored event targets whose anchor falls inside some scene's evidence span. `term_overlap_share` additionally requires the covering scene to repeat half the event label's distinctive words. | Not capture. A scene spanning the moment may describe something else, and a correctly worded summary that shares no vocabulary fails the overlap test. The 50% threshold is a chosen constant that has never been calibrated. |
| `unsupported_claims` | Three mechanical failures: assertions of a declared negative control; entities whose name occurs in none of the turns they cite; claims citing turn ids the session lacks. | Not a census. It sees only what an annotator declared absent and what contradicts its own citations. `in_transcript` separates an analysis that invented a term from one that repeated a recognizer's invention — the second is a recognition failure and is scored nowhere. |
| `surfaced_errors` | Of the errors this harness detected, how many the run raised a review question about — by evidence span for a missed target, by naming the term for a control. | Inherits every bound above it, and is silent about the largest class of important error: a scene that confidently describes the wrong thing. Nothing here detects one. |
| `processing_time` | `wall_clock_s` from the run report, and the realtime factor against the annotated excerpt. | One machine, whatever else was running. Excludes acquisition, conversion and model loading outside the timed region. |
| `peak_memory` | **Not measured.** Nothing in this repository records memory. | The gap is named in the report: a peak-RSS reading covering `RUSAGE_CHILDREN` as well as `RUSAGE_SELF`, since the recognizer is a subprocess, added to the run report that `run-audio` writes. |
| `question_count` | The review queue length, and its rate per recorded hour. | A count, not a quality. A run that asks nothing scores best and may have missed everything, which is why it is only readable beside `surfaced_errors`. |
| `review_burden` | **A proxy.** Questions and scenes priced at assumed per-item seconds, per recorded hour, against the personal-alpha target in `docs/PRODUCT.md`. | Not a review time. Both constants are assumptions and no human has been timed reviewing a session this pipeline produced, so the absolute value means nothing. Only its direction does. |

### Contamination is behaviour, not a warning

`truth.contaminating_providers` names engines that helped build an answer key. Scoring one
of them against that key marks it against its own output, so the harness withholds every
dimension that reads the key and reports the rest. The value is computed and then not
printed: a number beside a warning is still a number somebody quotes.

Identity is read from provenance *and* from the engine-native artifacts, at any depth. A
manifest names a provider to model precision (`whisper.cpp large-v3-turbo`); a session
records the provider's composed name in provenance and the model file two levels inside
the artifact. A check reading only the obvious places does not fire, and a contamination
check that never fires is worse than none because it looks like one.

The check fails closed in two ways, both of which the first real run needed:

- a session recording nothing that identifies its engines is `undetermined`, not clean;
- a session that identifies an engine *family* but not the model, where everything it does
  record agrees with a declared provider, is also `undetermined`. Being consistent as far
  as anyone can see is not the same as being cleared.

Fixture-provider output is refused separately and for a different reason: it is declared
truth being replayed, so scoring it measures whoever wrote the fixture.

### Timelines

A manifest anchor is an offset into published media; a session's turns are offsets into
whatever file was recognized. The harness picks between the two hypotheses by which one
actually lands anchors inside the session, and reports the choice.

When neither hypothesis lands an anchor, the session and the manifest are not describing
the same audio, and **every** figure derived from an anchor is withdrawn — not one of
them. An anchor read against the wrong clock does not fail loudly; it returns zero, and a
zero here is indistinguishable from a run that captured nothing. Concretely:

- `plot_capture` is unmeasurable, anchor coverage being its only mechanical handle;
- `surfaced_errors` is unmeasurable whenever a missed target carries an anchor, because
  otherwise every miss reads as unsurfaced — an accusation made on evidence that cannot be
  read;
- `entity_capture` keeps `recall_by_name`, which is lexical and consults no clock, and
  drops the anchor-corroborated lower bound instead of reporting it as zero.

The partial version of this guard — protecting `plot_capture` alone while the other two
printed confident zeros — shipped in the first draft of this harness and was caught by the
goal validator on PR #43.

### What the corpus cannot currently measure

Both annotated items — Hiddengrid and Mystic Horizon — declare `whisper.cpp large-v3-turbo`
contaminating, and that is the recognizer the pipeline runs. **No clean capture measurement
of the pipeline's own stack is obtainable from this corpus today.** The baseline in
`research/b05-scoring-baseline.md` records what that looks like in practice. Closing it
needs an answer key built without the engine under test, not a change to the harness.

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
