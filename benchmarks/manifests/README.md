# Benchmark manifests

Version `0.1` manifests describe reproducible public or synthetic test cases without
embedding media. The schema is
[`benchmark-manifest.schema.json`](../schema/benchmark-manifest.schema.json).

Validate every committed manifest:

```bash
uv run python scripts/validate_benchmark_manifests.py
```

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

## B01 candidates

- `critical-role-c3e01-jrusar-introductions.json`: polished studio video, strong public
  navigation and transcript aids, but no recorded redistribution permission.
- `hiddengrid-swc-ep044-tower-play.json`: archived amateur online actual play with an
  explicit CC BY-NC-ND 4.0 notice and direct published audio.

The Hiddengrid excerpt is the R0 recommendation because the direct source and explicit
license make acquisition reproducible. B02 must retain the original download privately,
process it noncommercially, use the manifest's logical time window, attribute the
creator, and avoid publishing a clip or other adapted audio unless separate permission
is obtained. Its timestamps and truth targets remain provisional until B02 performs a
fresh-cache listen-through and checksum report.
