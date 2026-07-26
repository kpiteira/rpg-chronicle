# R01: provisional speech stack — scorecard, probe evidence, and recommendation

Access review: 2026-07-26. Every external claim below is source-linked and dated. Every
number under "Measured" was observed on the operator's machine by
`research/probes/speech_stack_probe.py`; nothing measured is quoted from a project's
own README.

Probe machine: Apple M4 Pro, 12 cores, 24 GB unified memory, macOS 26.3.1, Python 3.12.

> **Read this first.** These probes measure *cost and output shape*, not accuracy.
> Word error rate needs reference transcripts the benchmark corpus does not have yet
> (`research/benchmark-candidates.md` leaves that to B02). Nothing here is a quality
> ranking, and the recommendation is provisional in exactly that sense.

## Recommendation

**Recognition: `whisper.cpp` with Metal, running `ggml-large-v3-turbo`.**
**Diarization: `sherpa-onnx` offline speaker diarization, at a low clustering threshold,
and labelled as unreliable downstream.** It is the only ungated local option probed and
it runs within budget, but the probe shows it does not currently recover the true
speaker count at any setting. See "Diarization is the unsolved half" — this is adopted
as the best available placeholder, not as a solved component.
**Alignment: not a separate component.** Every recognizer probed emits timestamps
natively, so the WhisperX-style wav2vec2 alignment stage buys nothing here and costs a
third model plus a second inference pass.

### Why not Parakeet, which measured faster

`parakeet-mlx` was the fastest and lightest thing probed, by a lot: 1.8x whisper.cpp's
throughput on the 600 s window (41.0x realtime against 23.3x) on a fifth of the memory,
widening to 3.7x throughput at 40 minutes — where the memory advantage narrows to about
45% (1,100 MB against 2,419 MB), because chunked Parakeet grows and whisper.cpp barely
does.
It is not a close call on those axes and this recommendation does not pretend otherwise. It goes to whisper.cpp on four grounds, in
order of weight:

1. **Speaker attribution — a real but smaller advantage than the raw numbers suggest.**
   Parakeet's unit is a sentence; whisper.cpp's is a shorter decoder segment. Raw mean
   speaker overlap was 0.85 for whisper.cpp against 0.61 for Parakeet, but that
   comparison is confounded and the corrected figures are 0.94 against 0.86 — see
   "Speaker attribution, corrected" below, which sets out both the confound and what
   survives it. `docs/PRODUCT.md` requires separating physical speakers, and whisper.cpp
   is still ahead, but this reason carries less weight than the raw gap implied.
2. **Long audio works by default.** Parakeet-mlx builds one tensor for the whole file
   and **fails outright at 20 minutes** — Metal refused a 14.4 GB allocation against a
   14.3 GB limit. It handles four hours only once an explicit `chunk_duration` is set,
   which is fine when you know, and a silent cliff when you do not. whisper.cpp windows
   internally and needed no parameter at any length probed.
3. **The portability floor.** MLX is Apple Silicon and nothing else. whisper.cpp runs
   the same workload on CPU, CUDA, ROCm and Vulkan from one codebase, and the CPU floor
   was measured, not assumed.
4. **Licence and obligation.** MIT throughout, against Apache-2.0 code over a CC-BY-4.0
   model that carries an attribution obligation into anything shipping its output.

Speed is not the binding constraint at 20x realtime, so trading it for the four
properties above is the right trade at this stage — and if that stops being true, the
replacement triggers below say exactly when.

One fact makes this cheaper to reverse than it looks: **whisper.cpp v1.9.0 added NVIDIA
Parakeet support**, and the Homebrew build ships a `parakeet-cli`. Choosing whisper.cpp
does not foreclose the Parakeet model — it reaches it through a portable runtime. What
that CLI does not yet have, per its own `--help` on v1.9.1, is JSON output, word
timestamps, or confidence, so it is not usable for this pipeline today.

## What the probes actually showed

### Cost

Measured on the 0–600 s window of Hiddengrid Episode 044 (`benchmarks/manifests/
hiddengrid-swc-ep044-tower-play.json`), 16 kHz mono. Full results in
`research/probes/results/`; text and engine-native artifacts are withheld there because
the source is CC BY-NC-ND.

| Stack | Wall clock | Realtime factor | Peak RSS | Units emitted | Unusable units | Load avg at start |
|---|---|---|---|---|---|---|
| `whisper-cpp-metal` | 25.8 s | 23.3x | 2,096 MB (child) | 302 | 1 | 6.7 |
| `parakeet-mlx` | **14.7 s** | **41.0x** | **429 MB** | 158 | 0 | 15.4 |
| `mlx-whisper` | 44.3 s | 13.6x | 2,058 MB | 450 | **104** | 12.6 |
| `faster-whisper-cpu` | 163.9 s | 3.7x | 2,644 MB | 240 | 0 | 4.7 |
| `sherpa-diarization` | 30.8 s | 19.5x | 3,654 MB | 208 spans | — | 6.7 |

Three readings of that table, in order of how much they change the decision.

**Parakeet is the fastest and lightest by a wide margin, and it still does not win.**
It is 1.8x faster than whisper.cpp here and uses a fifth of the memory; on the longer
inputs below the throughput gap widens to over 3x. But both are 20–41x
realtime on a task that needs to finish overnight at worst, so neither speed nor memory
is the product's binding constraint, and an advantage on a non-binding axis does not
decide anything. Recording this plainly matters: the recommendation goes to the slower
engine, and a reader deserves to see the number that argues against it.

**Speaker attribution splits them, but by less than the raw numbers say.** See the next
section — the raw overlap comparison is confounded by unit span, and correcting for it
shrinks a 0.24 gap to 0.08.

**The CPU floor is real, not theoretical.** faster-whisper on CPU alone ran at 3.7x
realtime — a four-hour session in roughly 65 minutes with no GPU at all. A stack that
degrades to that is portable in practice and not only on paper.

Wall-clock figures are upper bounds: a second agent session was running on the same
machine throughout, at the load averages recorded in the last column. Peak memory is
unaffected by contention.

### Speaker attribution, corrected

The first version of this scorecard led with raw mean speaker overlap — 0.85 for
whisper.cpp against 0.61 for Parakeet — as the main reason to prefer the slower engine.
The goal validator found that comparison confounded, and it was right. The correction
is recorded here rather than quietly applied, because the original number is the kind
that looks decisive and is not.

**The confound.** The diarizer's spans over the 600 s window total 407,621 ms. That is
the *sum* of spans, which double-counts wherever the model hears two people at once; the
union — the time anybody was actually speaking — is **384,502 ms**, and the probe now
records both. Parakeet's units span 477,520 ms, which is 93 seconds *more* than anyone
was speaking, because a sentence-level unit runs across the pauses inside it. Overlap is
measured against the unit's own span, so Parakeet cannot reach 1.0 no matter how
correctly every label is assigned. whisper.cpp's units total 389,060 ms, comfortably
inside the diarized speech, so its ceiling is 1.0. The two engines were being scored
against different maxima.

**The correction.** `speaker_coverage_ratio` — the share of a unit that *any* speaker
covers — was already computed per unit but never aggregated, which is why the confound
was invisible in the committed evidence. It is now reported, along with overlap divided
by coverage, which is attribution purity given what was diarized at all.

Read the last column as a summary rather than a statistic: it is the ratio of two
aggregate means, not the mean of per-unit ratios, so the third decimal carries less
information than it appears to. It is used here only to order stacks that the raw column
ordered misleadingly.

| Stack | Unit span | Raw overlap | Coverage | Overlap given coverage |
|---|---|---|---|---|
| `whisper-cpp-metal` | 389,060 ms | 0.847 | 0.900 | **0.941** |
| `mlx-whisper` | 317,200 ms | 0.636 | 0.667 | 0.952 |
| `faster-whisper-cpu` | 311,700 ms | 0.819 | 0.881 | 0.930 |
| `parakeet-mlx` | 477,520 ms | 0.610 | 0.712 | 0.857 |

**What survives.** whisper.cpp still attributes better than Parakeet, by 0.084 rather
than 0.237. `mlx-whisper` scores highest on this corrected measure and should be
discounted rather than believed: in the committed run it emitted 450 units of which
**104 could not become turns at all**, so its coverage denominator is built from a much
smaller set of usable units than the others'. Earlier runs of the same audio during this
goal produced 213 and 226 units with 1 unusable; those runs were overwritten by later
regenerations and are **not** in this diff, so treat the swing as an observation rather
than as evidence — the committed 450/104 stands on its own, and it is enough to
discount the row. That is a real advantage pointing the same way as before, but a
modest one — and the honest reading is that the four recognizers cluster between 0.86
and 0.94 on attribution purity, where the raw numbers suggested a chasm.

**What the low coverage means, since it is not purely an artifact.** A unit spanning
28% non-speaker time is a genuinely worse carrier for a single speaker label: attach one
name to it and the label describes silence and possibly a second voice as well. So
Parakeet's coarse units are a real liability for attribution — just a *different* one
from misattribution, and a third of the size the first number implied.

### Output shape and normalizability

Every stack's native output projects onto `TranscriptTurn`
(`src/rpg_chronicle/model.py`) without an information-losing transformation:

| Canonical field | whisper.cpp | parakeet-mlx | mlx-whisper | faster-whisper |
|---|---|---|---|---|
| `start_ms` / `end_ms` | `offsets.from` / `offsets.to`, already ms | `sentence.start` / `.end`, seconds | `segment.start` / `.end`, seconds | `segment.start` / `.end`, seconds |
| `text` | `segment.text` | `sentence.text` | `segment.text` | `segment.text` |
| `confidence` | mean of non-special `token.p` (needs `-ojf`) | `sentence.confidence`, native | `exp(avg_logprob)` | `exp(avg_logprob)` |
| `physical_speaker` | none — fused from diarization | none — fused from diarization | none — fused | none — fused |

Three things this table hides, and they matter:

1. **`confidence` is not one quantity.** Parakeet emits a native token confidence.
   The Whisper family does not: what is recorded for it is a decoder log-probability,
   which is the model's certainty about the next token, not about the transcription
   being right. Same 0–1 range, different meaning. A review layer that thresholds on
   "confidence" across engines is comparing incomparable things, and the canonical
   field should carry its provenance.
2. **No engine produces `physical_speaker`.** Speaker identity is a separate model, a
   separate run, and a fusion step. `fuse_speakers()` in the probe assigns each ASR unit
   the speaker it overlaps most and records `speaker_overlap_ratio` alongside — because
   an ASR segment that straddles a speaker change gets a label that is an attribution
   rather than an observation, and the review layer needs to be able to tell.
3. **Rejected units are real.** `TranscriptTurn.__post_init__` rejects empty text and
   non-positive spans. The probe reports what could not become a turn rather than
   dropping it; a `TranscriptProvider` will hit the same cases. On the 600 s
   window whisper.cpp produced 1 unusable unit out of 302, while mlx-whisper produced
   **104 out of 450** on the same audio. Parakeet and faster-whisper rejected none
   anywhere. So the rate is not a property of the pipeline but of the engine and the
   run, which is exactly why a provider that assumed every segment converts would pass
   its own tests and then meet a file where a quarter of them do not.

### What a `TranscriptProvider` would have to do

Integration is out of scope for this goal, so this is a mapping description rather than
code. A `WhisperCppTranscriptProvider` implementing the `transcribe(source) ->
TranscriptResult` protocol in `src/rpg_chronicle/providers.py` would:

1. convert the source to 16 kHz mono WAV with ffmpeg — the recognizers accept other
   formats, but resampling inside the engine hides its cost from measurement;
2. run `whisper-cli -m ggml-large-v3-turbo.bin -f <wav> -ojf -of <prefix>`, keeping the
   full JSON as `TranscriptResult.native_artifact`, which satisfies
   `docs/ARCHITECTURE_BOUNDARIES.md`'s requirement to retain the engine-native artifact;
3. run diarization separately and fuse by maximum temporal overlap, exactly as
   `fuse_speakers()` in the probe does;
4. build `TranscriptTurn` per segment: `offsets.from`/`offsets.to` straight into
   `start_ms`/`end_ms`, `text` stripped, `confidence` as the mean of non-special token
   probabilities, `physical_speaker` from the fusion;
5. surface, not swallow, the units that cannot become turns.

Two things the current canonical model does not carry, which this probe shows it will
need. Both are `src/rpg_chronicle/model.py` changes, so both belong to the TPM rather
than to this role, and both are proposed rather than made here:

- **confidence provenance.** `TranscriptTurn.confidence` is a bare float. A native
  Parakeet confidence and an `exp(avg_logprob)` are different quantities in the same
  range, and nothing downstream can currently tell them apart.
- **attribution quality.** `physical_speaker` is a bare label with no indication of how
  much of the turn it covers. The probe records `speaker_overlap_ratio` beside it
  because, on the measured diarization, two thirds of turns from some stacks carry a
  label that describes only part of the turn.

### The finding that changes the product, not the stack

On the rights-clear synthetic clip — where the truth is the generator's script, which no
engine ever sees — all four recognizers failed identically on the thing this product
exists to capture.

The clip's proper nouns come in two kinds, and they must not be averaged together. Four
are **coined** — `Vaelthorn`, `Ilyra`, `Brann`, `Korrigan` — strings no English lexicon
contains, which a recognizer has to reconstruct from phonemes alone. Two are **names
built from ordinary words** — `Ashen Spire`, `Warden` — which a recognizer can produce
without knowing they are names at all. An earlier version of this table scored all six
together and reported "2 of 6 recovered"; the goal validator pointed out that this
softens the result, and it does. Separated:

| Stack | **Coined nouns recovered** | English-word names | Control phrases |
|---|---|---|---|
| `whisper-cpp-metal` | **0 of 4** | 2 of 2 | 4 of 4 |
| `parakeet-mlx` | **0 of 4** | 2 of 2 | 4 of 4 |
| `mlx-whisper` | **0 of 4** | 2 of 2 | 4 of 4 |
| `faster-whisper-cpu` | **0 of 4** | 2 of 2 | 4 of 4 |

The real number is zero: not one engine recovered a single coined proper noun, while
every engine recovered every ordinary-word name and every control phrase. But "zero
recall" flattens a range worth seeing, so the probe commits what each engine produced
instead (`what_was_produced_instead` in `synthetic-scores.json`):

| Expected | whisper.cpp | parakeet-mlx | mlx-whisper / faster-whisper |
|---|---|---|---|
| `Vaelthorn` | Vealthorn | Veelthorn | Ealthorn |
| `Ilyra` | Eilera | Eyleira | Eilera |
| `Brann` | Bran | Bran | Bran |
| `Korrigan` | Karikon | **Kari can** | Karikon |

`Brann` → `Bran` is a one-letter homophone; `Korrigan` → `Kari can` is a word-boundary
failure that turns a name into a clause. Calling all four the same kind of failure would
be overstating it. What is true of all four is the part that matters here: **none is
usable as an entity key without correction**, and a spelling that is nearly right is no
more matchable than one that is wrong. The failure is specific to invented vocabulary and
it is not an engine defect — it is what a general-purpose recognizer with no campaign
lexicon does.

Two consequences, and the second is the important one.

1. **Engine choice cannot fix this.** Four engines, two model families, zero coined
   nouns recovered between them.
   Swapping recognizers is not the lever; campaign vocabulary is. That is already an
   owned concern in `docs/ARCHITECTURE_BOUNDARIES.md` ("campaign vocabulary and
   correction history"), and this measurement is the first evidence of how much work it
   has to do.
2. **Confidence does not flag the error.** An earlier version of this scorecard reported
   a 0.02 gap between "recovered the name" and "mangled the name". That number was an
   artifact: the scorer put a truth turn carrying one recovered and one lost noun into
   *both* buckets, which necessarily flattens the difference. The goal validator caught
   it. With mixed turns excluded, no clean contrast can be computed on this clip at all
   — because no coined noun survived anywhere, there are zero turns in the "recovered"
   bucket.

   What the clip does support is a comparison against each stack's own typical turn:

   | Stack | Mean confidence on turns that lost a coined noun | Corpus mean | Corpus minimum |
   |---|---|---|---|
   | `whisper-cpp-metal` | 0.936 | 0.952 | 0.827 |
   | `parakeet-mlx` | 0.961 | 0.976 | 0.918 |
   | `mlx-whisper` | 0.819 | 0.827 | 0.812 |
   | `faster-whisper-cpu` | 0.818 | **0.742** | 0.082 |

   Turns that mangled a proper noun score within 0.01 of a typical turn on three stacks,
   and 0.08 *above* typical on faster-whisper. Every stack's minimum confidence sits at
   or below what its name-losing turns score — 0.082 against 0.818 on faster-whisper — so
   a low-confidence threshold surfaces other turns first and reaches these last, if ever.

   A caveat on these four rows specifically, stated with its real size: Whisper-family
   decoding is not deterministic, and re-running this probe moved `faster-whisper-cpu`'s
   corpus mean between 0.63 and 0.80 and its minimum between 0.02 and 0.46 across runs.
   That is a swing of most of the range, not of a decimal place. The *direction* held in
   every run — name-losing turns never scored low enough to be flagged — and that is the
   only part of this table worth relying on. Only the run committed in
   `research/probes/results/` is reproducible from this diff. Since `docs/PRODUCT.md` makes "confidence and
   consequence determine intervention" a product principle, a review layer ranking
   questions by engine confidence will rank these errors as safe — inverting what it is
   for. Review prioritization needs a signal other than decoder confidence for
   entity-bearing turns.

This is the most consequential finding in the goal, and it is about the product rather
than about which engine to borrow.

## Diarization is the unsolved half

Recognition is a solved borrowing problem. Diarization is not, and the probe was run
specifically to find that out rather than to infer it from project claims — the goal
named it as the most likely place for a stack to look good on paper and fail in
practice. It failed in practice.

### It does not recover the speaker count, at any setting

On the synthetic clip, where four speakers are known by construction, sweeping
`sherpa-onnx`'s clustering threshold never produces four:

| Threshold | Labels found (truth: 4) | Mean turn purity | Two people merged into one label? | One person split across labels? |
|---|---|---|---|---|
| 0.4 | 6 | 0.949 | no | GM, PLAYER_A, PLAYER_B |
| 0.5 | 6 | 0.923 | no | GM, PLAYER_A, PLAYER_B |
| 0.6 | 6 | 0.907 | no | all four |
| 0.7 | **3** | 0.975 | **yes — two labels each carry two people** | PLAYER_A, PLAYER_B |
| 0.8 | **3** | 0.954 | **yes** | PLAYER_A, PLAYER_B |
| 0.9 | **2** | 0.972 | **yes** | PLAYER_A, PLAYER_B |

The count jumps from six to three with nothing in between. Note that mean purity *rises*
as the result gets worse: purity measures whether a turn got a consistent label, and
merging two people into one label makes labels more consistent and less true. A tuning
loop optimizing purity would walk straight into the failure.

The two failures are not equivalent, and that asymmetry is the actionable part:

- **Fragmentation** (low threshold) makes one person look like two. It is recoverable —
  a later merge, a voice profile, or a single human correction fixes it, and
  `docs/PRODUCT.md` explicitly prefers "a useful anonymous transcript over failed
  perfect diarization".
- **Collision** (high threshold) makes two people look like one. It silently attributes
  one player's words to another, which is a fabricated fact in the campaign record, and
  no downstream correction can find it without re-listening.

**Therefore: run at a low threshold and accept fragmentation.** The default 0.5 is on
the right side of that line. Tuning upward to make the speaker count "look right" would
be optimizing the metric against the product.

### Telling it the answer makes it worse

The obvious product mitigation is to ask: the user knows how many people are at the
table. Supplying `num_clusters=4` on the four-speaker clip returns **three** labels, and
both of them collide — GM and PLAYER_C share one, PLAYER_A and PLAYER_B share the other.
Constraining the count converts a recoverable failure into two unrecoverable ones. The
mitigation is worse than the default, and it is worth knowing that before building a
setup prompt around it.

### On real audio the knob moves but there is nothing to aim at

The 600 s Hiddengrid window produced **23 distinct speaker labels** at the default
threshold, and the count climbs with input length — 23 at 10 minutes, 32 at 20, 39 at
30, 46 at 40, on a podcast with a handful of participants. Sweeping the threshold does move it:

| Threshold | 0.4 | 0.5 (default) | 0.6 | 0.7 | 0.8 | 0.9 |
|---|---|---|---|---|---|---|
| Labels on 600 s of Hiddengrid | 35 | 23 | 17 | 11 | 7 | 4 |

So the count is tunable on real audio — but the episode has no verified speaker count
(`benchmarks/manifests/hiddengrid-swc-ep044-tower-play.json` records
`expected_physical_speakers: null`), so there is nothing to tune *toward*. And the one
input where the truth is known is the one where no setting reaches it. Tuning this knob
against a plausible-looking number would be fitting to a guess.

### A number in the scored results that looks like good news, and is not

`research/probes/results/synthetic-scores.json` reports a mean turn purity of 1.0 with
zero colliding labels for the Whisper-family stacks on the synthetic clip. Read
straight, that contradicts this whole section. It should not be read straight.

Purity there is computed over *fused* turns, and fusion has already collapsed each ASR
unit to a single winning speaker. On a clip whose turn boundaries line up with silences,
each truth turn overlaps exactly one fused unit, so purity is 1.0 almost by
construction — it is measuring the fusion step, not the diarizer. The same metric run
against the raw diarizer spans, which is the honest comparison, gives 0.923 with six
labels for four speakers.

Where fused purity is genuinely informative is *between* stacks on the same diarization,
because it then reflects unit granularity rather than diarization quality. That is the
comparison in the cost section, and it comes with its own confound, handled there.

### One honest caveat about the synthetic evidence

Text-to-speech voices may be adversarial for speaker-embedding models trained on natural
speech: synthetic voices lack the vocal-tract variation the embeddings key on, so the
synthetic clip may *understate* real diarization quality rather than overstate it. That
cuts against this section's conclusion and is recorded because it does. It does not
rescue the Hiddengrid result, which is natural speech and worse, nor the `num_clusters`
result, which is a failure of a mechanism rather than of an acoustic condition. B02's
annotated truth on real audio is what would settle it.

The fusion aggregates say the same thing from the other side: at 600 s, 90 of 301
whisper.cpp turns carry a speaker label covering less than 80% of the turn, and 10 turns
got no label at all.

### What this means for the recommendation

`sherpa-onnx` is still the right provisional choice, for reasons that are about
availability rather than quality: it is the only local diarizer probed that needs no
Hugging Face account and no gated-model acceptance, it is Apache-2.0 over MIT and
Apache-2.0 models, and it runs at ~20x realtime inside a memory budget the machine has.
pyannote is the reference implementation the field measures against and would very
likely do better, but it puts an account and a per-model conditions acceptance in the
setup path — a real cost for a local-first personal project, and one worth paying only
once diarization is known to be the limiting factor. It now is, which is why the
replacement trigger below is written to fire.

Downstream consumers must treat `physical_speaker` from this stack as a low-confidence
hint. `speaker_overlap_ratio` is recorded per turn precisely so the review layer can
tell an observation from an attribution.

## Four-hour projection

The goal asks that measured figures permit a four-hour projection rather than a guess.
They were therefore measured at four input lengths, not one, because the interesting
question is the *shape* of the curve and a single point cannot show it. Every figure is
from `research/probes/results/scaling-*.json`.

| Input | whisper.cpp | parakeet-mlx (chunked) | sherpa diarization |
|---|---|---|---|
| 10 min | 25.8 s (23.3x) / 2,096 MB | 14.7 s (41.0x) / 429 MB *(unchunked)* | 30.8 s (19.5x) / 3,654 MB |
| 20 min | 53.4 s (22.5x) / 2,202 MB | 16.1 s (74.4x) / 1,123 MB | 55.5 s (21.6x) / 5,157 MB |
| 30 min | — | — | 80.5 s (22.4x) / 5,972 MB |
| 40 min | 111.9 s (21.4x) / 2,419 MB | 30.8 s (78.0x) / 1,100 MB | 105.3 s (22.8x) / 6,295 MB |

At 20 minutes unchunked, Parakeet does not appear in this table because it does not run:
`research/probes/results/scaling-parakeet-unchunked-1200s.json` records the failure,
1.5 s in, with `[metal::malloc] Attempting to allocate 14401440032 bytes which is
greater than the maximum allowed buffer size of 14302248960 bytes`. Its chunked figures
above use `chunk_duration=120`, recorded in each result's `configuration` block.

**Time is linear in input length.** Every stack held a stable realtime factor across a
4x range — whisper.cpp within 21.4–23.3x, diarization within 19.5–22.8x. Residual
variation tracks the machine's load average rather than the input, which is why the load
is recorded in every result. Chunked Parakeet is the exception in a good way: it gets
*faster* per second of audio on longer inputs, 41.0x to 78.0x, because a fixed model-load
cost spreads over more work.

**Projected four-hour wall clock**, taking the *slowest* observed factor for each stage:

- recognition, whisper.cpp at 21.4x → **11.2 minutes**
- diarization, sherpa-onnx at 19.5x → **12.3 minutes**
- **total, run sequentially: about 24 minutes for a four-hour session**, on a machine
  that was busy throughout.

For comparison, the same projection is 3.1 minutes for chunked Parakeet, and 65 minutes
for the CPU-only floor. Even the floor finishes a night's session inside an hour and a
half.

**Memory needs two different projections, because the two stages behave differently.**

- *whisper.cpp is effectively constant.* Growth is 0.179 MB per second of audio, and it
  is 0.177 MB/s between 10→20 minutes and 0.181 between 20→40, so a straight line is
  the right model. Four hours projects to **about 4.6 GB**. This is the internal 30-second
  windowing doing its job.
- *sherpa-onnx diarization decelerates.* Growth per second of audio fell 4.97 → 2.50 →
  1.36 → 0.54 MB across the four intervals, roughly halving each time. These are
  *interval* slopes between consecutive measurements, not averages: the first is
  (3653.6 − 922.3) MB ÷ (600 − 50) s, using the 50 s synthetic measurement as the low
  anchor. Dividing a single measurement by its own duration gives a different and
  less useful number. That gives a
  range rather than a number, and both ends are stated because the extrapolation is the
  weakest link in this projection:
  - **lower bound ~6.6 GB**, if the halving continues;
  - **upper bound ~12.8 GB**, if growth instead stays flat at the last observed rate.

Run sequentially, peak memory is the larger stage, so a four-hour session should need
**7–13 GB against the machine's 24 GB**. That fits, with less headroom than is
comfortable — and the upper bound is the one to plan against.

**Assumptions this projection makes, stated so they can be checked:**

1. A four-hour recording behaves like a scaled-up 40-minute one. Untested beyond 40
   minutes; the decelerating memory curve is where this could break.
2. Speech density is comparable. Hiddengrid is an edited podcast; a real table has more
   silence, which should help both stages.
3. The stages run sequentially. Running recognition and diarization concurrently would
   halve the wall clock and *add* the memory, pushing the upper bound past 17 GB — and
   the machine was observed deep into swap during the 40-minute diarization run with a
   second agent session present. That swap reading came from `sysctl vm.swapusage` at the
   time and is **not** in any committed artifact — the probe records RSS and load average,
   not swap — so treat it as a caution rather than as evidence. Sequential is the
   recommended default regardless, on the memory arithmetic alone.
4. No model reload per session; load time is under 2 s and irrelevant at this scale.

**The escalation threshold in the goal was not reached.** A four-hour session processes
in roughly 24 minutes inside the machine's memory, so cloud processing of private
recordings does not need to be put to the user.

## Scorecard

Two groups, because they are not the same kind of thing. The first group is components
that could be wired behind `TranscriptProvider`. The second is applications that solve
a nearby problem, whose value to this project is architectural evidence rather than
code — the goal asked for reusable components, and honest scoring means saying which
of these are not that.

Coverage against the subjects named in `agents/reuse-research.md`: Handy, Squire,
Speakr, Scriberr, noScribe, WhisperX and related diarization/alignment projects, and Omi
are all below. The related-projects clause is read as pyannote.audio, sherpa-onnx,
NVIDIA NeMo and WhisperKit/SpeakerKit; `faster-whisper`, `mlx-whisper`, `whisper.cpp`
and `parakeet-mlx` were added because they are what the applications on that list
actually run underneath.

### Components

Stars, licences, and last-push dates come from the GitHub API on 2026-07-26, not from
project self-description.

| Component | Capability | Licence (code / model) | Maintenance (last push) | Integration cost | Observable output | Hardware fit |
|---|---|---|---|---|---|---|
| [whisper.cpp](https://github.com/ggml-org/whisper.cpp) 52.3k★, v1.9.1 (2026-06-19) | ASR, VAD, `tinydiarize` speaker-turn markers, **and NVIDIA Parakeet since v1.9.0** | MIT / MIT (ggml Whisper weights) | active, 2026-07-11 | low — `brew install whisper-cpp`, CLI with JSON output, no Python dependency at all | segments with ms offsets and per-token probabilities (`-ojf`) | Metal + Core ML/ANE on Apple Silicon; CUDA, ROCm, Vulkan, OpenVINO; **plain CPU** |
| [parakeet-mlx](https://github.com/senstella/parakeet-mlx) 965★ + [nvidia/parakeet-tdt-0.6b-v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) | ASR, 25 European languages, auto language ID | Apache-2.0 / **CC-BY-4.0** | active, 2026-06-05; no tagged releases | low — `pip install parakeet-mlx`, native sentence/token objects | sentences and tokens with start/end and **native confidence** | **Apple Silicon only** (MLX). The *model* runs on NVIDIA via NeMo and on any whisper.cpp backend; this runtime does not port. No CPU path. |
| [mlx-whisper](https://pypi.org/project/mlx-whisper/) 0.4.3 (2025-08-29) | ASR | MIT / MIT | active (MLX team) | low — one function call | segments, word timestamps, `avg_logprob`, `no_speech_prob` | Apple Silicon only |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) 24.5k★ | ASR, Silero VAD, batching | MIT / MIT | **last push 2025-11-19 — over eight months quiet**, despite an active-looking issue tracker | low | segments, word timestamps and per-word probability | CUDA 12 + cuDNN 9 for GPU; **CPU everywhere**; no Metal — on Apple Silicon it is CPU-only |
| [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) 13.8k★ | offline speaker diarization, ASR, TTS, VAD | Apache-2.0 / segmentation MIT, embedding Apache-2.0 | active, 2026-07-24 | low — pip wheel, **no Hugging Face token and no gated model** | speaker spans with start/end/label | CPU (ONNX Runtime); NPU backends; no Metal or CUDA path in the published wheel |
| [pyannote.audio](https://github.com/pyannote/pyannote-audio) 10.3k★ | diarization, VAD, overlap detection, embeddings | MIT / MIT but **gated** | active, 2026-07-24 | **medium — the pretrained pipeline requires a Hugging Face account, an access token, and accepting per-model user conditions** | speaker spans; the reference implementation the field is measured against | CPU and CUDA; benchmarked on H100 |
| [WhisperX](https://github.com/m-bain/whisperX) 23.3k★ | faster-whisper + wav2vec2 word alignment + pyannote diarization | BSD-2-Clause | active, 2026-07-13 | medium — three models, and diarization inherits pyannote's gate; its ASR core is the quiet faster-whisper | word-level timestamps, speaker labels | CUDA 12.8 recommended; **Apple Silicon supported only in CPU mode** |
| [WhisperKit](https://github.com/argmaxinc/WhisperKit) 6.3k★ | ASR on Core ML; SpeakerKit adds pyannote-v4 diarization | MIT | active, 2026-07-13 | **high for this project — Swift, macOS 14+/iOS 18+**; a Swift CLI behind a Python pipeline is a process boundary and a second toolchain | word and segment timestamps | Apple Silicon, Core ML/ANE. The best-fitting *platform*, the worst-fitting *language*. |
| [NVIDIA NeMo](https://github.com/NVIDIA-NeMo/NeMo) 17.8k★ | ASR (Parakeet, Nemotron) and diarization | Apache-2.0 | active, 2026-07-26 | high — heavyweight framework, CUDA-oriented install | full pipeline artifacts | **NVIDIA GPU + CUDA recommended for inference; no Apple Silicon support stated.** Strongest on NVIDIA, unavailable here. |

Hardware support, stated per the goal's request so a later hardware decision starts from
recorded evidence:

| Component | Apple Silicon | Discrete NVIDIA | CPU-only |
|---|---|---|---|
| whisper.cpp | yes — Metal, plus optional Core ML/ANE encoder | yes — CUDA | **yes, first-class**; also ROCm, Vulkan, OpenVINO |
| parakeet-mlx | yes — the only target | no | no |
| mlx-whisper | yes — the only target | no | no |
| faster-whisper | CPU only (no Metal backend in CTranslate2) | yes — CUDA 12 + cuDNN 9, its strongest configuration | yes, with `compute_type=int8` |
| sherpa-onnx diarization | CPU on Apple Silicon (no Metal path in the wheel) | not in the published wheel | **yes, and it is the only mode probed** |
| pyannote.audio | CPU or MPS | yes, its benchmark target | yes |
| WhisperX | CPU only on macOS | yes — CUDA 12.8 recommended | yes, `--compute_type int8 --device cpu` |
| WhisperKit | yes — Core ML/ANE | no | Apple-platform CPU only |
| NeMo | not supported | yes — its design target | possible but not practical |

### Applications (evidence, not components)

| Project | Licence | Last push | What it shows | Why it is not a component here |
|---|---|---|---|---|
| [Handy](https://github.com/cjpais/Handy) 27.6k★ | MIT | 2026-07-25 | Whisper via `transcribe-cpp` and **Parakeet V3 via `transcribe-rs`** — independent confirmation that both recognizers are viable desktop engines | Dictation scope: no timestamps, no diarization. Rust/Tauri. Nothing to lift. |
| [Squire](https://github.com/elrobis/squire) 0★, 4 commits | **none declared** | 2025-10-06 | The closest domain match found: Whisper → pyannote 3.1 → LLM character attribution → scene summaries. Its stage decomposition matches this repository's boundaries, which is mild independent validation of the architecture | Absent a licence there is no permission to reuse the code, and four commits is not a dependency. Architectural evidence only. |
| [Scriberr](https://github.com/rishikanthc/Scriberr) 2.9k★ | MIT | 2026-06-01 | Parakeet/Canary/Whisper plus diarization in a self-hosted app | **Maintenance paused** per the project's own notice. A paused dependency is a liability, not a shortcut. |
| [noScribe](https://github.com/kaixxx/noScribe) 2.1k★ | **GPL-3.0** | 2026-07-21 | faster-whisper + pyannote packaged for non-technical researchers on Apple Silicon; a good source of practical defaults | GPL-3.0 is a copyleft obligation this MIT repository should not take on by linking. |
| [Speakr](https://github.com/murtaza-nasir/speakr) 3.5k★ | **AGPL-3.0** | 2026-07-15 | A consumer of WhisperX-as-a-service; confirms the ASR-service seam is a common shape | It delegates recognition rather than performing it, and AGPL-3.0 reaches further than GPL. No engine to borrow. |
| [Omi](https://github.com/BasedHardware/omi) 13.1k★ | MIT | 2026-07-26 | Capture firmware and mobile apps for a wearable | **Transcription is cloud (Deepgram)**, which the consent policy in `docs/CAPTURE.md` rules out, and its capture target is a wearable rather than a stationary iPad. |

## Licence and redistribution notes for downstream consumers

- **Nothing recommended is gated.** whisper.cpp weights, the ggml models, sherpa-onnx's
  segmentation and embedding models all download without an account. This is a real
  operational property: the probe ran on a machine with no Hugging Face token
  (verified — no `HF_TOKEN`, no `~/.cache/huggingface/token`), and pyannote's own
  pipeline would have failed there.
- **pyannote's models are MIT but gated.** The gate is an access-control step, not a
  licence restriction; sherpa-onnx redistributes an ONNX export of
  [`pyannote/segmentation-3.0`](https://huggingface.co/pyannote/segmentation-3.0)
  (MIT) through GitHub releases, which the licence permits. A consumer choosing
  pyannote directly inherits the account requirement.
- **The Parakeet model is CC-BY-4.0**, which carries an attribution obligation that MIT
  code does not. Anything shipping Parakeet output should name the model.
- **`sherpa-onnx-reverb-diarization-v1`** is offered as an alternative segmentation model
  and was not probed. Its upstream,
  [`Revai/reverb-diarization-v1`](https://huggingface.co/Revai/reverb-diarization-v1),
  is gated and carries a custom "other" licence rather than a standard one — the terms
  were not read, so nothing is claimed about them here beyond the fact that they need
  reading before use.
- **ffmpeg** performs audio conversion in this pipeline. The Homebrew build reports
  `--enable-gpl --enable-version3` and `ffmpeg -L` states GPL v3, so it is copyleft: fine
  for a binary invoked as a subprocess, not fine to link into a distributed application.
- **The benchmark input remains restricted.** Hiddengrid Episode 044 is CC BY-NC-ND with
  redistribution restricted; no audio, clip, or transcript of it appears in this
  repository, and the probe results drawn from it carry only aggregate metrics.

## Rejected, and why the rejection might expire

| Rejected | Reason | The rejection stops holding when |
|---|---|---|
| `mlx-whisper` | measurably the slowest Apple Silicon path for the same Whisper model | it closes the gap with whisper.cpp's Metal backend |
| `faster-whisper` on this machine | no Metal backend, so Apple Silicon means CPU | CTranslate2 gains a Metal backend, or the pipeline moves to NVIDIA hardware — where it becomes a leading candidate |
| WhisperX | its alignment stage duplicates timestamps the recognizers already produce, and its diarization inherits pyannote's account gate | word-level alignment quality is shown to limit evidence linking, or diarization moves to pyannote anyway |
| WhisperKit / SpeakerKit | Swift toolchain and a process boundary against a Python pipeline | the product acquires a native macOS surface, at which point it is the strongest platform fit on this list |
| NVIDIA NeMo | no Apple Silicon support; needs CUDA for practical inference | processing moves to a machine with a discrete NVIDIA GPU |
| pyannote.audio directly | account gate and per-model conditions, for a diarization quality advantage not yet measured against sherpa-onnx | sherpa-onnx diarization is shown to be the limiting factor, which the probe evidence above shows |
| Scriberr, noScribe, Squire, Speakr, Omi as code sources | paused maintenance, GPL-3.0 copyleft, no licence, no engine, and cloud transcription respectively | — these are ecosystem evidence and their rejection is about reuse, not about merit |
| Whisper `tinydiarize` | produces speaker-*turn* markers, not speaker identity; it cannot say the same person spoke twice | never for this product's purpose — it answers a different question |

## Replacement triggers

Measurable conditions under which the provisional choice stops being right. These are
the terms on which this recommendation should be revisited.

**Switch the recognizer to `parakeet-mlx` when** any of:

- a four-hour session on the target machine exceeds 30 minutes of recognition wall clock,
  or recognition peak RSS exceeds 8 GB — Parakeet's measured 78.0x realtime and 1.1 GB
  at 40 minutes (chunked) buy real headroom the moment either becomes binding;
- Parakeet's native token confidence is shown to separate wrong turns from right ones
  better than whisper.cpp's token probabilities on annotated audio. The synthetic clip
  showed neither doing so; if one of them does on real audio, that decides it;
- whisper.cpp's segment granularity is shown *not* to be the reason its speaker overlap
  is higher, removing the one measured advantage behind this recommendation.

**Switch the recognizer to `faster-whisper` or `WhisperX` when** processing moves to a
machine with a discrete NVIDIA GPU. On CUDA they are the mature path and their
Apple-Silicon penalty disappears; watch that faster-whisper's repository has been quiet
since 2025-11-19 before depending on it.

**Switch the recognizer to WhisperKit when** the product grows a native macOS surface.
At that point the Swift toolchain stops being a cost and Core ML/ANE stops being
unreachable.

**Replace the whole recognizer tier when** coined-proper-noun recall stays at zero
*after* campaign vocabulary is in place. That would mean the problem is the acoustic
model rather than the lexicon, and fine-tuning or a different model family becomes the
lever instead of more vocabulary.

**Move diarization off `sherpa-onnx` when** either:

- the cluster count on a known-speaker-count recording stays above the true count by
  more than one after threshold tuning — the condition currently observed;
- pyannote's community pipeline is measured to beat it on the same audio by enough to
  justify accepting a Hugging Face account requirement into the setup path.

**Escalate to the user — not to a different component — when** no local stack can
process four hours within a plausible envelope on this hardware. The goal names that as
a product decision, because the alternative is cloud processing of private recordings
and `docs/CAPTURE.md` makes that a consent question rather than a technical one. **That
threshold was not reached.** The four-hour projection clears it by a wide margin, so this
escalation is recorded as not triggered rather than as pending.

## What this research did not establish

- **Accuracy.** No word error rate, no diarization error rate against annotated truth on
  real audio. B02 owns the reference annotations that would make those computable.
- **The target acoustic condition.** Both probe inputs are wrong in different
  directions: Hiddengrid is an edited podcast with music, the synthetic clip is
  noiseless text-to-speech. Neither is a single iPad in a room, which is
  `docs/EVALUATION.md` corpus tier 3 and remains an explicit gap.
- **Whether diarization is good enough to be useful.** The probe shows it is currently
  not, on this input, with these settings. It does not establish whether that is the
  input, the settings, or the models.

## Proposed follow-up outcomes

Candidates for the TPM to weigh, prioritize, or discard. This role recommends; it does
not schedule.

1. **Integrate the recommended stack behind `TranscriptProvider`.** The goal excluded
   this deliberately. The mapping above is the specification; the work is real and
   nobody else is holding it.
2. **Carry confidence provenance and attribution quality in the canonical model.** Two
   fields in `src/rpg_chronicle/model.py`, which is the TPM's shared boundary, and both
   are needed before a review layer can act on either signal without being misled.
   Consumer evidence for the request is in this document.
3. **Diarization is the open research problem, not recognition.** Recognition is
   borrowable today. Speaker identity is not, and the highest-value next probe is
   pyannote's community pipeline against sherpa-onnx on B02's annotated audio — which
   also settles whether the account gate is worth accepting.
4. **Campaign vocabulary has a measured job to do.** Coined-proper-noun recall is
   currently zero of four, and this scorecard's synthetic clip is a cheap, rights-clear
   regression input for measuring progress against it.
5. **`docs/STATUS.md` records that no provisional engine is selected.** That is now out
   of date, and `docs/` is TPM territory, so it is flagged here rather than edited.
6. **A tier-3 benchmark input does not exist.** Every conclusion about the target
   acoustic condition is currently an extrapolation from two inputs that are wrong in
   opposite directions. This belongs to benchmark-research.
