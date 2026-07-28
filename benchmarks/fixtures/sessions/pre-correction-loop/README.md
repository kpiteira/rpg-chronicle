# A session written before the correction loop existed

Produced by running

```
uv run rpg-chronicle run-fixture benchmarks/fixtures/r0_synthetic_session.json --output <dir>
```

on `main` at c92680c — the commit A02 branched from, before any file in
`src/rpg_chronicle/review/` existed.

**One field was edited.** `source.path` held the absolute path of the machine that ran
it, including a username, which has no business in a public repository and nothing reads.
It now holds the repository-relative path to the same fixture. Nothing else was touched,
and the edit cannot weaken what this payload demonstrates: that is the *absence* of
`needs_attention[].id`, `needs_attention[].status`, and `provenance.corrections`, none of
which is reachable from a source path.

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
