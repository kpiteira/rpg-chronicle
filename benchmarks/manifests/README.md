# Benchmark manifests

Version `0.1` manifests describe reproducible public or synthetic test cases without
embedding media. The schema is
[`benchmark-manifest.schema.json`](../schema/benchmark-manifest.schema.json).

Validate every committed manifest, from the repository root:

```bash
uv run python scripts/validate_benchmark_manifests.py
```

Every manifest is reported on its own line as `valid: <path>` or as a failure naming the
file and the reason: `<parse>` for a file that is not valid JSON, `<read>` for a file that
cannot be decoded, a field path for a schema violation, and `<semantic>` for a rule the
schema cannot express. One bad file fails the run with exit status 1 without hiding the
findings for the other manifests.

## Fetching the media

A manifest that records `source.media_sha256` and `source.media_bytes` can be reproduced:

```bash
export RPG_CHRONICLE_BENCHMARK_CACHE=/your/private/benchmark/cache
uv run python scripts/fetch_benchmark_media.py <manifest id>
```

The script downloads into the private cache, digests the result, and compares it with the
manifest. On a difference it quarantines the download as `*.mismatch` — `*.mismatch.2`,
`*.mismatch.3` and so on when an earlier quarantine is already there, so evidence from a
previous run is never overwritten — and exits non-zero:
the recorded digest is not updated and no other source is substituted, because every truth
anchor is an offset into the recorded bytes. Report the difference on the benchmark goal
issue instead.

## Truth targets

A target is `verified` only when it was observed in the recording. The validator enforces
what that means, because prose cannot:

- `anchor_ms` is required and must fall inside the excerpt window;
- `basis` must be `audio_observed` (a human ear) or `audio_machine_assisted` (the recording
  read through tooling) — a target inferred from a title, description, or index stays
  `provisional`, whatever the annotator believes. The two verifiable values stay separate
  so a consumer reading the field alone can tell machine-read truth from heard truth;
- `evidence` must say what was observed;
- `truth.method` must record how the truth was established, including which provider
  produced any machine-assisted output;
- `truth.contaminating_providers` must name every provider that helped build the truth
  once any target is machine-assisted, so a scoring run can refuse to mark an engine
  against its own output;
- `source.media_sha256` must be present once any target is verified. An anchor is an
  offset into particular bytes, and without a digest a later reader cannot tell whether
  they still have those bytes;
- `rights.license_url` must be present when `rights.local_processing` is `permitted` — a
  claim that a licence allows processing has to point at the licence that says so.

Read licence and publication facts from the source's own markup, on the page that carries
the notice: not from a feed, an aggregator, a rendered summary, or a prior manifest. Two
manifests in this corpus have already carried a wrong licence or a wrong publication date
that came from a secondary source.

A candidate ruled out on rights is recorded, not deleted, with `r0_status: rejected` and
the reason. `music_or_effects: null` is the honest value for such a candidate: nothing was
listened to, and `false` would claim an observation nobody made.

`recording_conditions.capture_layout` states only what the recording establishes.
`single_mixed_track` says there is no per-speaker channel to diarize from and claims
nothing about where the speakers were; that belongs in `observations` with its evidence.
`expected_physical_speakers` is the upper reading and `proven_distinct_speakers` the
floor — the true count lies between, and the two can be far apart. Proving *k* distinct
people requires *k* speakers established as pairwise distinct from one another; a chain
of "these two are different" observations, however long, can be satisfied by two people.

`kind: person` is a physical speaker; `kind: character` is the fiction they voice. Keeping
them apart in the corpus is what lets a result distinguish the two later.

## Scope

The schema keeps source identity and access evidence, a logical excerpt, recording
conditions, reference readiness, truth targets, and rights review together. These are
inputs to later processor and product-level evaluation; a manifest is not a result.

`rights.local_processing` and `rights.redistribution` are explicit review states, not
legal conclusions. `unknown` blocks automated fetching or redistribution until the
project records permission or a reviewed basis.

Time windows use half-open millisecond ranges: `start_ms <= t < end_ms`. Selecting a
logical window does not require writing a clipped media file. This matters for
NoDerivatives sources.

Downloaded media, clips, transcripts, processor output, and runtime annotations belong
under the configured private `benchmark_cache`; the repository ignore rules cover the
default `benchmark-cache/`, `audio/`, `artifacts/`, and common media extensions.

## The corpus

[`../notes/corpus-coverage.md`](../notes/corpus-coverage.md) states what these items can
and cannot diagnose together, which gaps remain, and what closing each would take. Read it
before adding a candidate — the corpus is optimised for diagnostic diversity, not size, so
a new item has to name a failure mode nothing else exposes.

- `critical-role-c3e01-jrusar-introductions.json`: polished studio video, strong public
  navigation and transcript aids, but no recorded redistribution permission.
- `hiddengrid-swc-ep044-tower-play.json`: archived amateur online actual play with an
  explicit Creative Commons notice and direct published audio. B01 recorded that notice as
  CC BY-NC-ND 4.0; B02 checked the episode page's raw HTML and corrected it to
  CC BY-NC-SA 3.0 Unported.

The Hiddengrid excerpt is the R0 recommendation because the direct source and explicit
license make acquisition reproducible. Retain the original download privately, process it
noncommercially, use the manifest's logical time window, attribute the creator, and do not
publish a clip or other adapted audio without separate permission — ShareAlike would allow
an attributed noncommercial derivative, but the recording also embeds Shadowrun material
owned by Topps, which the site's licence cannot sublicense.

B02 completed the listen-through: the fetch is checksum-verified, the 0–600 000 ms window
was kept on measured grounds rather than by default, and the truth targets are anchored
observations instead of title-derived guesses. Read
[`../notes/hiddengrid-swc-ep044-tower-play.md`](../notes/hiddengrid-swc-ep044-tower-play.md)
before scoring anything against it: annotation there is machine-assisted, and the note
names the engines that therefore cannot be scored against it without declaring the
dependency. The Critical Role candidate's targets remain provisional and metadata-derived.

## B03 candidates

- `mystic-horizon-ch1ep1-killing-zombozos.json`: 3 h 57 m in one continuous livestreamed
  file under CC BY 3.0 — the multi-hour tier, at the product's real target duration.
- `dice-and-die-lmop-e01-stranger-danger.json`: unpolished amateur play under CC BY 3.0,
  clipping at +2.2 dBFS, following a published adventure whose proper nouns give an
  independent spelling reference.
- `kix-dnd-amateurs-first-session.json` and `oxventure-wyrdwood-campaign.json`: rejected,
  Standard YouTube Licence, kept with their reasons so the question is not reopened from
  scratch. The KIX rejection is on licence rather than merit and is the best candidate to
  seek permission for.

Both admitted items are unannotated. They establish admissibility; annotating either is a
separate outcome, as B02 was for Hiddengrid.
