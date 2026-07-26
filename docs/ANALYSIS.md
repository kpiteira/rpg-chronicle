# Model-backed analysis: architecture, cost, and what was measured

Last updated: 2026-07-26. Produced under goal #12 (`agent:review-analysis`).

## What this document is, and is not

It **is** a record of what a four-hour-scale analysis pass costs, how the abstraction
behind it is arranged, and what a real model did with a synthetic transcript containing
deliberately planted long-range structure.

It **is not** evidence of analysis quality on real recorded play. No real session has
been recorded, transcribed, or analysed. The fixture is authored, the transcript is
synthetic, and the noise around its story beats is templated. Quality on real play is a
separate goal and requires a selected transcription engine and fetched audio, neither
of which exists yet. Every number below is a measurement of *scale and structure*.

All model output quoted here is exactly that — model output, not declared truth.

## The three concerns, and why they are separate

The `AnalysisProvider` seam (`docs/DECISIONS.md` D-008) said analysis would be a
replaceable provider. This goal built the first real one, and it separates three things
that are commonly fused:

| Concern | Where it lives | Changing it means editing |
|---|---|---|
| Which model is asked | configuration on a backend | one constructor argument |
| How the model is reached | `analysis/backend.py` + one implementation | one class |
| How a long transcript is split and recombined | `analysis/decompose.py` | one module |

`analysis/prompts.py` holds what is asked, in RPG terms, and knows no vendor.
`analysis/provider.py` composes the three by their interfaces. The only module naming a
vendor is `analysis/claude_cli.py`, plus `cli.py` where a backend is chosen — which is
where D-008 already put selection.

The design test the goal set was: *adding an OpenRouter backend later must not require
touching the decomposition code, the prompts, or anything under `pipeline.py`.* That is
checked mechanically by `tests/test_vendor_neutrality.py`, which scans the source of
every module that must survive a change of vendor and fails on the commit that leaks
one. It has already caught one leak — a comment in `provider.py` naming the model used
for a measurement.

### The transport

`ClaudeCliBackend` reaches Claude through a headless `claude -p` process, because the
operator holds a subscription and the repository already invokes a headless session
this way in `scripts/validate-goal.sh`. The invocation is deliberately stripped down:

> A default headless `claude -p` invocation carries its own system prompt, tool
> definitions, project settings, and MCP configuration: **~35,000 tokens** before any
> transcript is added. With `--system-prompt`, `--tools ""`, `--strict-mcp-config` and
> `--setting-sources ""`, the same round trip costs **188 tokens** of fixed overhead.

Measured, not estimated. Without that, transport overhead would have been a third of
the figure this goal exists to produce.

## The decomposition strategy, and when it engages

Turns are rendered one per line as `[turn-00740] (speaker-3) text`, packed into windows
that fit a token budget, with a configurable tail of turns repeated across each
boundary so a scene that straddles one is seen whole. Each window is analysed
independently. When there is more than one window, a synthesis pass assembles the
window findings into a single session account; when there is only one, the window
result *is* the session result and no synthesis request is made.

**It did not engage on a four-hour session.** At the default budget the entire
transcript fit in a single request, with room to spare. The seam exists and works — it
is exercised below by lowering the budget — but the answer to the goal's question is
that a four-hour transcript did not need it.

### The planning heuristic was wrong by 1.68x

Window planning happens before any request, so it cannot use a tokenizer a backend
owns. It estimated characters-per-token at the usual prose figure of 4.0. Measured over
this fixture the real figure was **2.38** — because every line carries a turn id and a
speaker label, and `[turn-02940] (speaker-3)` costs far more tokens per character than
the sentence after it. Citation scaffolding is roughly a third of the payload.

The constant is now 2.5, erring toward planning more windows than needed. Erring the
other way builds a request the backend rejects, which costs the whole run.

## Cost, measured

Reproduce with:

```bash
uv run python scripts/generate_long_session.py \
  --output benchmarks/fixtures/generated/long_synthetic_wrackford.json

uv run rpg-chronicle run-fixture \
  benchmarks/fixtures/generated/long_synthetic_wrackford.json \
  --output /tmp/long --analysis model --cost-report /tmp/cost.json
```

Add `--max-input-tokens 30000` for the decomposed variant. The generator is
deterministic, so the fixture is byte-identical on every machine.

**Fixture**: 3,247 turns, 32,760 words, 4.00 hours, 171,300 transcript characters,
260,511 characters once rendered with citations and instructions.

**Model**: `claude-sonnet-5`, reached through the operator's Claude Code subscription.

| | One request (default) | Decomposed (`--max-input-tokens 30000`) |
|---|---|---|
| Requests | 1 | 5 (4 windows + 1 synthesis) |
| Input tokens (billed) | **109,474** | **136,871** (+25%) |
| Output tokens | 12,115 | 56,148 (×4.6) |
| Wall time | **126 s** | **596 s** (×4.7) |
| Scenes produced | 12 | 23 |
| Review questions | 3 | 5 |
| Format retries | 0 | 0 |

### Against the 60–80k working estimate

The goal recorded an operator estimate of 60–80k input tokens for a four-hour session.
The measured figure is **109,474 — between 37% and 82% above it**. The gap is the same
citation scaffolding that broke the planning heuristic: the estimate was arithmetic on
words of speech, and the request also carries 3,247 turn ids, 3,247 speaker labels, and
the instructions.

**It does not change the load-bearing conclusion.** A single context window remains a
safe assumption for a four-hour session with a wide margin, so decomposition is not on
the critical path for M2. It would matter for a backend with a 128k context, where
109k of input plus output leaves very little headroom.

Two minutes and roughly 120k tokens for a four-hour session is, in the author's
judgement, comfortably within "routine". The trade-off between analysis depth and
per-session cost remains the user's to make, and it can now be made against this
number rather than against a guess.

### Decomposition is worse here, on every axis measured

Splitting a transcript that fits produced 25% more input tokens, 4.6x the output, 4.7x
the wall time, and twice as many scenes at a finer grain. It found two additional
plausible questions. Nothing in this measurement recommends decomposing a transcript
that fits in one request; the seam is there for transcripts that do not.

## Was the planted long-range structure captured?

Reported as a measurement, with the model's own words. **This is not asserted in any
test**, and no test asserts that a summary contains particular fixture text — such a
test would restate the fixture and prove nothing (`agents/goal-validator.md`, tautology
check). `tests/test_long_fixture.py` asserts only that the *fixture* still contains the
plants and that they are genuinely far apart.

The fixture plants four things. See `benchmarks/fixtures/long_session_plan.json` for
each plant and how to assess it.

### 1. The callback — captured

An iron object is traded away in the first twenty minutes; three and a half hours later
the only defence against the drowned host is a bell that cannot ring for want of a
clapper. Nothing between the two mentions the object.

> "Ondry confesses he stopped the tithe, silenced the warning bell by removing its
> clapper, and threw the clapper into the river above the drowned mill. **The party
> realizes, in horror, that the iron object they traded to Halgrim was that very
> clapper.**"

Connected explicitly, not merely mentioned twice. Also captured under decomposition,
where the two halves fell in different windows and only the synthesis pass could join
them.

### 2. One entity under two names — captured, but only after a fix

Villagers in the first hour speak of "the Weir Mother". In the final hour a voice names
itself "Anhalla". No line in the session links them; the evidence is that both are owed
a tithe at the same ford across the same sixty years.

**The first run missed it entirely** — both were named in the summary as unrelated
powers, and no question was raised. Diagnosing that produced the most useful
architectural finding of this goal:

> The instructions about callbacks and same-entity aliases lived only in the *synthesis*
> prompt. Synthesis runs only when there is more than one window. A four-hour session
> fits in one window. **The most valuable question the system can ask was only ever
> requested on the code path that does not execute.**

The fix was general, not fixture-specific: the cross-cutting rule now appears in both
prompts. Nothing in either prompt names a bell, a clapper, a weir, or a tithe. After
the fix:

> "Is the water entity 'Anhalla' the same being as 'the Weir Mother' invoked by the old
> woman at the ford at the very start of the session?"
> — recommendation: "Treat them as the same entity: both are tied to the same
> ford/river tithe, the same sixty-year cycle, and the same 'give something or it takes
> what it likes' logic." (confidence 0.7, consequence high)

Raised under decomposition too, at confidence 0.5.

This is exactly what the plant was built to detect, and it detected a real defect. It is
also the clearest available warning about how much of this system's value rests on
prompt content that no test can pin down.

### 3. Transcription drift on a central name — captured

The village is "Wrackford" in most turns and "Rackford" in a few.

> "The village's name is repeatedly misheard as 'Rackford' before being corrected to
> 'Wrackford' — is 'Wrackford' the definitively correct spelling for campaign records?"
> — recommendation: "Use 'Wrackford,' as the GM explicitly spells it out ('with a W')."
> (confidence 0.9, consequence medium)

Raised once, with a recommendation, rather than once per occurrence.

### 4. Speakers versus characters — captured

One player voices a character for the whole session and takes over a hireling when that
character is downed; the game master voices every non-player character.

> "A four-person party (Brannoc, Tovald, and Sela, run by speaker-2, speaker-3, and
> speaker-4 respectively, with speaker-1 as GM)"

Speaker labels and character names stay distinct, and the two characters voiced by one
player are not merged.

### The one thing the first run asked about was the wrong thing

Before the fix, the single question raised was whether a character survives a
cliffhanger — a deliberately open ending, not an error to confirm. The prompt now says
so explicitly. Worth recording because it is the failure mode the attention budget is
most vulnerable to: a question that looks responsible and spends attention on nothing.

## The attention budget held

The queue is capped at 10 questions by default, derived in `docs/UX.md` from the
five-minute north-star review target. Both runs came in under it without the cap
binding: 3 questions in one request, 5 decomposed. The cap is enforced in
`provider.py`, not requested in the prompt — a model asked for at most ten usually
returns at most ten, and "usually" is not a bound.

## Evidence discipline held, and cost two runs to get there

`model.py` rejects claims citing turns that do not exist. The provider satisfies that
check, never routes around it, and is *stricter*: a claim from one window may not cite
a turn from another, because it never saw it.

Two failures in real runs are worth recording, because both looked like the check being
too strict and only one was:

1. **Renormalised turn ids.** Under decomposition the model cited `turn-740` for a turn
   rendered `turn-00740`. The run aborted. This is the right turn in the wrong format,
   like wrapping bare JSON in a code fence. `TurnIdResolver` now resolves leading-zero
   differences only, and only when the canonical form maps to exactly one real id;
   anything ambiguous or nonexistent still aborts. The prompt also now says to copy ids
   character for character.
2. **A literal newline inside a JSON string.** Parsing now permits control characters
   inside string values, which changes what counts as well-formed syntax and nothing
   about what counts as a supported claim.

Neither softens the evidence check. An invented citation still aborts the run, is never
retried, and `tests/test_model_analysis.py` pins the boundary: a padding variant of a
turn that does not exist still raises.

An unparseable reply is retried once, and the retry is counted in the cost report. An
unsupported claim is never retried — retrying that would be sampling until the model
stops getting caught.

## Proposed decision entry — not adopted here

`docs/DECISIONS.md` is TPM-owned and this goal does not write to it. The following is
**proposed** for the TPM's assessment.

> **D-0xx: Subscription-mediated analysis is not third-party reproducible**
>
> The first real `AnalysisProvider` reaches a model through the operator's Claude Code
> subscription. This is in tension with D-001, which puts reproducible aggregate results
> in a public repository: a third party can clone this repository, generate the fixture
> byte-identically, and read every prompt — but cannot reproduce the model output or the
> cost figures without their own subscription and their own money.
>
> The tension is accepted with three mitigations, all of which exist today: the fixture
> and its generator are public and deterministic; the prompts are in the repository and
> vendor-neutral; and the backend seam is narrow enough that an API-key or gateway
> backend is one class, so a third party who wants reproducibility can buy it directly
> rather than reimplement the pipeline.
>
> What is *not* mitigated: the numbers in `docs/ANALYSIS.md` are one operator's
> measurements on one date against a model that will change under them. They should be
> treated as a scale reading, not a benchmark, and re-measured when the model changes.

## Follow-ups this goal did not do

- **Analysis quality on real recorded play.** Explicitly out of scope; needs a selected
  engine and real audio.
- **Entity extraction as a first-class field.** The provider recovers entities, aliases,
  and unresolved threads from every window and they reach `processor-native/analysis.json`,
  but `CanonicalSession` has no field for them, so they do not reach the review package.
  The alias question above was generated from material the canonical model cannot
  currently carry. That is now a consumer need backed by a fixture, which is what
  `docs/ARCHITECTURE_BOUNDARIES.md` asks for before the shared boundary changes — but it
  is the TPM's call, so no field was added.
- **A second backend.** Out of scope by the goal. The seam is proved with a fake.
- **Prompt regression testing.** The alias miss was found by reading output, not by a
  test, and could regress silently. Pinning prompt behaviour needs a scoring approach
  that does not become a tautology, which is a benchmark-research question.
