# A session written before the correction loop existed

Produced by running

```
uv run rpg-chronicle run-fixture benchmarks/fixtures/r0_synthetic_session.json --output <dir>
```

on `main` at c92680c — the commit A02 branched from, before any file in
`src/rpg_chronicle/review/` existed. Both files are copied here verbatim.

It is committed rather than regenerated because regenerating it with current code would
test nothing: the point is to load a payload this repository actually wrote under the
older behaviour, not one shaped by hand to survive. Two things about it are load-bearing
and are why it is worth keeping:

- `review-package.json` carries no `id` and no `status` on its `needs_attention` entries.
  Both were added by this goal, because an answer has to name what it is answering.
- `canonical-session.json` carries no `provenance.corrections` block, because nothing had
  ever been corrected.

Nobody's speech is in it. It derives from `benchmarks/fixtures/r0_synthetic_session.json`,
which is invented.
