# Scoring baseline, 2026-07-28

The first run of `rpg-chronicle score`, recorded against `main` at c92680c so that the two
goals changing the pipeline beside this one — name uncertainty and the correction loop —
have something to be compared to. `docs/EVALUATION.md` describes what each dimension is and
what it does not mean; this file records what the instrument returned and what running it
exposed.

Everything here is an aggregate. Per-target results quote the answer key, so the full JSON
reports are written to the content directory and stay out of this repository
(`docs/CONTENT_AUDIT.md`, `docs/GOAL_RULES.md` R1).

## What was run

Real audio, reproducible by anyone holding the content directory:

```bash
uv run python scripts/fetch_benchmark_media.py hiddengrid-swc-ep044-tower-play
ffmpeg -v error -y \
  -i "$HOME/.rpg-chronicle/benchmark-cache/hiddengrid-swc-ep044-tower-play/HIDDENGRID_EP044_S028_P01_140524.mp3" \
  -ss 0 -t 600 -ac 1 -ar 16000 -c:a pcm_s16le "$HOME/.rpg-chronicle/work/b05/hiddengrid-window.wav"
uv run rpg-chronicle run-audio "$HOME/.rpg-chronicle/work/b05/hiddengrid-window.wav" \
  --output "$HOME/.rpg-chronicle/work/b05/runs" \
  --session-id hiddengrid-swc-ep044-b05-baseline \
  --no-diarize \
  --run-report "$HOME/.rpg-chronicle/work/b05/run-report.json"
uv run rpg-chronicle score \
  --session "$HOME/.rpg-chronicle/work/b05/runs/hiddengrid-swc-ep044-b05-baseline" \
  --manifest hiddengrid-swc-ep044-tower-play \
  --run-report "$HOME/.rpg-chronicle/work/b05/run-report.json" \
  --report "$HOME/.rpg-chronicle/benchmarks/results/b05-hiddengrid-baseline.json"
```

The fetch verified byte for byte against the digest B01 recorded — 127266240 bytes,
sha256 `2a0f5272…ac37e9`, unchanged since 2026-07-26 — so the anchors in that manifest
still address the audio they were written against.

Diarization was skipped. `sherpa_onnx` is not installed in this environment, and speaker
attribution is not among the dimensions M2 names, so the run went ahead without it rather
than stopping. It is a real gap in the run and not in the harness: nothing scored here
would change.

Synthetic, reproducible by anyone with the repository and no content directory at all:

```bash
uv run rpg-chronicle score \
  --session benchmarks/fixtures/scoring/session-baseline \
  --manifest benchmarks/fixtures/scoring/manifest.json
```

## Baseline: Hiddengrid episode 044, first ten minutes

Recognition by whisper.cpp large-v3-turbo, analysis by claude-sonnet-5 through the
`claude-code-cli` backend. 301 turns, 5 scenes, 3 review questions.

**The verdict was withheld.** The manifest declares `whisper.cpp large-v3-turbo` among its
contaminating providers, and that is the recognizer that produced the run, so every
dimension that reads the answer key was computed and not reported.

| Dimension | Value | State |
|---|---|---|
| `entity_capture` | — | withheld: contaminated |
| `plot_capture` | — | withheld: contaminated |
| `unsupported_claims` | — | withheld: contaminated |
| `surfaced_errors` | — | withheld: contaminated |
| `processing_time` | 104.1 s wall, **5.76× realtime** | reported |
| `peak_memory` | — | not measured |
| `question_count` | **3** questions, 18.0 per recorded hour | reported |
| `review_burden` | **1410 s** per recorded hour (proxy) | reported |

Three notes on the numbers that were reported.

**5.76× realtime** is the first timing this project has on real audio through the whole
pipeline. It excludes acquisition and the conversion to 16 kHz mono, and it is one machine
on one afternoon. Extrapolating it to the four-hour target case gives roughly 42 minutes,
which is a useful order of magnitude and not a measurement of that case.

**Three questions over ten minutes** is 18 per recorded hour. Read it beside
`surfaced_errors`, which is withheld here: a low question count is only good news if the
run also found the things worth asking about, and this pairing is exactly what the
contamination refusal prevents anyone from checking on this item.

**1410 s per recorded hour** is 7.8× the personal-alpha target in `docs/PRODUCT.md`, and
the number is a proxy built on two constants nobody has measured. It should not be read as
"review is 7.8× too slow". It should be read as: the proxy is far enough from target that
calibrating it is worth doing, which is the open question at the end of this file.

## Baseline: the synthetic fixture

`benchmarks/fixtures/scoring/` is invented material — no recording, nobody's speech — built
so the harness has a full-dimension baseline that runs in CI and a set of deliberately
degraded variants to be checked against.

| Dimension | Baseline value |
|---|---|
| `entity_capture` | `recall_by_name` 0.75, `recall_anchor_corroborated` 0.75 |
| `plot_capture` | `coverage_upper_bound` 0.667, `term_overlap_share` 0.667 |
| `unsupported_claims` | 0 control hits, 0 unsupported entities, 0 dangling citations |
| `surfaced_errors` | 1 detected, 1 surfaced, 0 unsurfaced |
| `processing_time` | not measured (no run report — the fixture is not a run) |
| `peak_memory` | not measured |
| `question_count` | 1 question, 6.0 per recorded hour |
| `review_burden` | 630 s per recorded hour (proxy) |

## The harness discriminates

A harness that returns a plausible number for any input measures nothing. Three sessions,
each differing from the baseline in one deliberate way, scored against the same manifest.
Held by `tests/test_scoring.py::test_degradations_move_only_the_dimensions_they_damage`,
which asserts the non-moves as well as the moves.

| metric | baseline | turns removed | entity renamed | claim added |
|---|---|---|---|---|
| `entity_capture.recall_by_name` | 0.75 | **0.5** | **0.5** | 0.75 |
| `entity_capture.recall_anchor_corroborated` | 0.75 | **0.5** | **0.5** | 0.75 |
| `plot_capture.coverage_upper_bound` | 0.667 | **0.333** | 0.667 | 0.667 |
| `plot_capture.term_overlap_share` | 0.667 | **0.333** | 0.667 | 0.667 |
| `unsupported_claims.negative_control_hits` | 0 | 0 | 0 | **1** |
| `unsupported_claims.entities_absent_from_cited_turns` | 0 | 0 | **1** | **1** |
| `surfaced_errors.detected_errors` | 1 | **2** | **2** | **2** |
| `surfaced_errors.unsurfaced` | 0 | **1** | **1** | **1** |
| `question_count.review_questions` | 1 | 1 | 1 | 1 |
| `review_burden.est_seconds_per_recorded_hour` | 630 | **510** | 630 | 630 |

The columns that do not move are the load-bearing part. Renaming one entity moves entity
capture and the unsupported-claim count and leaves plot capture, the negative controls and
the question count exactly where they were. Adding an unsupported claim moves the claim
counts and leaves both capture figures untouched.

Two movements are worth naming because they look wrong and are not. A renamed entity is
both a miss and an unsupported claim — its name occurs in none of the turns it cites — so
two dimensions moving on one degradation is the instrument agreeing with itself. And
`review_burden` *falls* when turns are removed, because a damaged run produces fewer scenes
to review: the proxy prices attention, not quality, and a run that finds nothing is cheap
to review. That is a property of the dimension and the reason it is never read alone.

## The contamination rule as behaviour

Run against real corpus material, verbatim:

```
score: hiddengrid-swc-ep044-b05-baseline against hiddengrid-swc-ep044-tower-play
harness 0.1, verdict: WITHHELD
------------------------------------------------------------------------------
contamination: CONTAMINATED
    the truth in this manifest was built with whisper.cpp large-v3-turbo,
    which also produced this session. The run holds an undeclared advantage
    over any run that did not write the answer key, so every dimension that
    reads the answer key is withheld rather than printed with a warning
    beside it
```

The command exits 2, so a script cannot step over the refusal.

**This is where running beat asserting.** The first version of this check reported the run
CLEAN. Two defects, both found by pointing it at real material rather than at the fixture
that was built to satisfy it:

1. **The model was nested and the check never saw it.** `SpeechTranscriptProvider` writes
   its composed name at the top of the native artifact and the recognizer's `engine` and
   `model_file` one level down under `recognition`. A top-level read found
   `whisper.cpp (no diarization)` and `claude-sonnet-5`, matched nothing, and reported
   clean. The identity walk is now recursive to a bounded depth.
2. **Knowing the family and not the model counted as cleared.** Even with the recursion,
   a session that records `whisper.cpp` and no model is *consistent* with a declared
   `whisper.cpp large-v3-turbo`; the only thing separating them is detail the session did
   not record. That is now `undetermined` and withheld. The rule is per recorded string
   and asks whether the session's tokens are a strict subset of the declaration's, so
   `whisper.cpp` is not cleared against `whisper.cpp large-v3-turbo` and is cleared
   against `openai-whisper medium.en`, where the implementation token contradicts it.

The fixture had passed throughout. A fixture written by the same person as the check tests
the check against its author's model of the world, and that is the failure mode this
project keeps meeting from a new direction.

## Findings

**1. No clean capture measurement of the pipeline's own stack is obtainable from this
corpus.** Both annotated items — Hiddengrid and Mystic Horizon — name `whisper.cpp
large-v3-turbo` contaminating, and that is the recognizer `run-audio` runs. The corpus can
time the pipeline and count its questions on real audio; it cannot tell anyone how much of
the plot it captured. Closing this needs an answer key built without the engine under test.
It is not a harness change and the harness must not be relaxed to produce a number.

**2. The nearest uncontaminated answer key already exists, in another format.**
`benchmarks/fixtures/long_session_plan.json` carries four planted structures over a
twelve-beat synthetic session with an explicit `how_to_assess` for each — a long-range
callback, one entity under two names, transcription drift on a central name, and a
speaker/character separation. It is synthetic, so no engine contaminates it, and it is long
enough for the properties a ten-minute excerpt cannot exhibit. Two of the four plants are
partly mechanical and two are human judgements this harness cannot make. The file is review
and analysis's, and adapting it is annotation work that B05 was scoped out of; it is
recorded here as the cheapest route to finding 1.

**3. Contamination is declared per item, and truth provenance is per target.** Hiddengrid
carries five `audio_observed` targets among twenty-one — things a person heard, which no
engine wrote. A per-target rule would let those be scored on a contaminated item. The
harness deliberately does not do this, because the Hiddengrid method records that the human
was given the machine's hypothesis before listening, and B04 recorded a case of that
priming changing what was reported. A human confirming a machine's guess is not an
independent observation. If the corpus ever carries unprimed human targets, the rule is
worth revisiting; today the item-level refusal is the honest one.

**4. Memory is recorded nowhere.** Named precisely in the report rather than estimated: a
peak-RSS reading covering `RUSAGE_CHILDREN` as well as `RUSAGE_SELF` — the recognizer is a
subprocess and the parent's figure would miss the engine entirely — added to the run report
`run-audio` writes. That report belongs to the `run-audio` command, so B05 named the gap
instead of editing another goal's wiring.

**5. Engine identity is matched on the declared string, so implementation and weights are
one identity.** `whisper.cpp small.en` and `openai-whisper medium.en` are separate entries
in the Hiddengrid manifest, and the harness treats them as separate engines. A run of
whisper.cpp using medium.en weights would therefore not match the openai entry. Whether
that is correct is a question about what the corpus means by a contaminating provider, not
a bug in the matching: if the same weights under a different runtime should count, the
manifests need to say so, because the harness cannot infer it.

## Open question for the operator

`review_burden` is the one dimension that cannot be made honest without a person. Its two
constants — 45 s per review question, 20 s per scene — are assumptions, and the proxy
currently reports 1410 s per recorded hour against a 180 s target without anybody knowing
whether the constants are within a factor of three.

Calibrating it needs one timed review, and the specific ask is bounded: open the review
package from the run above — 5 scenes and 3 questions over ten minutes of audio — answer
the three questions, and report the wall time. Roughly five minutes. One data point does
not calibrate a constant, but it settles the order of magnitude, which is the difference
between a proxy that can be read and one that cannot.
