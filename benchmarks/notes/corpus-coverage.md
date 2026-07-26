# What the corpus can diagnose, and what it still cannot

Written at B03 (issue #14), 2026-07-26. Read with
[`../manifests/README.md`](../manifests/README.md), which describes the manifest rules,
and `docs/EVALUATION.md`, which names the tiers.

## Method, stated first because the order matters

Rights were determined **before** any audio judgement, for every candidate. The failure
this guards against is admitting a recording because it sounds right and handling the
licence afterwards, which produces a corpus that cannot legally be used.

Licence facts were read from each watch page's own markup on 2026-07-26, not from a
description, an aggregator, or a prior manifest — the lesson B02 paid for, where a
merged manifest carried the wrong licence for months.

**The detection was controlled.** A check that reports "no Creative Commons notice" is
worthless if it cannot see one. The same detection was run against videos that do carry
the notice and found `Creative Commons (reuse allowed)` on each, and `yt-dlp` reported
the licence field independently. So a negative result here is a real difference between
candidates, not a broken test.

Durations come from each file's own metadata, never from a description.

## The corpus after this goal

| Tier | Item | State |
|---|---|---|
| Polished professional | `critical-role-c3e01-jrusar-introductions` | Reference only; local processing unknown, targets provisional |
| Amateur online, edited | `hiddengrid-swc-ep044-tower-play` | **Scoreable.** Verified truth over a ten-minute window |
| Amateur online, unpolished | `dice-and-die-lmop-e01-stranger-danger` | Admitted, unannotated |
| Multi-hour stress | `mystic-horizon-ch1ep1-killing-zombozos` | Admitted, unannotated |
| Single room, single microphone | — | **Empty** |
| Controlled or degraded | `benchmarks/fixtures/r0_synthetic_session.json` only | No manifest, no real degraded audio |

### What it can now diagnose

- **Whether understanding survives length.** 3 h 57 m in one continuous livestreamed file, with no chapter break, re-setup, or edit concealing a discontinuity. This is the product's real target duration and the corpus had nothing near it.
- **Whether unpolished level handling breaks transcription.** The new amateur item clips at +2.2 dBFS across a 15.8 LU range; the existing amateur item was levelled to 8.2 LU in post. A pipeline that only works on produced audio should now be visible.
- **Fantasy-name accuracy against an independent reference.** The Dice & Die item plays a published adventure, so much of its proper-noun set has a canonical spelling documented outside the audio and outside any decoder that might be scored against it.
- **Entity and event capture on real, unrehearsed play**, against listened-through truth — still only on the Hiddengrid window.

### What it cannot

- **The product's actual recording condition.** Every item in the corpus is remote play mixed to a single track: Hiddengrid gated and levelled, Mystic Horizon over Discord, Dice & Die over Roll20. Not one is a room with people in it and a microphone on the table. The corpus can say a pipeline handles online actual play; it cannot yet say anything about an iPad on a table four feet from four people.
- **Deliberate degradation.** No item tests a known, controlled impairment.
- **Campaign-arc continuity.** Whether understanding carries across sessions is untested. The rejected Oxventure lead was proposed for this and would have suited it, licence aside.
- **Anything at all about the two new items' content.** They are admitted, not annotated. Their recording conditions are measured; their entities, events, and coherence are unknown.

## Is a genuine single-file long session still missing?

**No — that gap is filled.** `mystic-horizon-ch1ep1-killing-zombozos` is 3 h 57 m 18 s in
one file, streamed live, under CC BY. Measured, not read from a description.

Two qualifications. Nobody has listened to it, so its *suitability* rests on measurement
and the publisher's framing rather than on content. And it is remote play, so it tests
duration without testing the room.

The four-hour target is met at 3 h 57 m, and more length is available in the same campaign
— but "same channel, so same licence" is exactly the assumption this goal forbids, so the
siblings were checked one by one on 2026-07-26 rather than inferred:

| Episode | Duration | Licence, checked per video |
|---|---|---|
| Ch. 1 Ep. 6 (`4YNOvKwO0lU`) | 4:18:49 | CC BY |
| Ch. 1 Ep. 4 (`5LAVK0tpVEI`) | 4:14:22 | CC BY |
| Ch. 1 Ep. 16 (`8yW4k-TNnBM`) | 3:47:55 | CC BY |
| Ch. 1 Finale (`MIsnpf9L6Og`) | 3:14:38 | CC BY |

Those four are cleared. The rest of the sixteen-episode campaign is **not** — a licence is
set per video, and any further episode needs its own check before use.

## What it would take to close the remaining gaps

**Single room, single microphone.** The honest answer is that this is unlikely to be
solved by searching public video. What is published is overwhelmingly remote play, because
remote play is what streams. Three routes, in the order I would try them:

1. **Record one.** The user plays in a session and the product exists to serve exactly that recording. One evening's capture, with the consent policy in `docs/CAPTURE.md` already written, would produce the most representative item in the corpus and would carry no licence question at all. This is a product decision, not a research one.
2. **Ask a small creator.** `kix-dnd-amateurs-first-session` is rejected on licence, not on merit — an unedited three-and-a-half-hour livestream by self-described amateurs, closer to the target than anything admitted. A 58-view channel is exactly the kind of creator who might say yes to research use. Asking is the user's to do.
3. **Keep searching under the CC filter**, specifically for in-person table recordings. The filter works and the search is cheap; the yield for in-person play is the open question.

**Controlled degradation.** Cheapest of all, and it needs no new source: derive it from an
item already admitted, by applying a known, documented impairment to a private copy. That
is a benchmark-construction task, not a rights task, and it is the obvious next thing this
role can do without asking anyone for anything.

**Campaign-arc continuity.** The Mystic Horizon channel publishes a sixteen-episode
campaign under the same CC BY mark as the admitted episode. Consecutive episodes there
would give arc continuity with a rights position already determined — a much cheaper path
than seeking permission from a commercial rights holder.

## Every candidate evaluated

Every licence below was read from that candidate's own watch-page markup on 2026-07-26,
by the controlled check described above. The two candidates with no manifest of their own
carry their landing URL here so the determination is source-linked wherever it is recorded.

| Candidate | Duration | Licence, from page markup | Verdict |
|---|---|---|---|
| KIX, *Our First Session* — [`PrNE4_ZHRig`](https://www.youtube.com/watch?v=PrNE4_ZHRig) | 3:24:46, was live | Standard YouTube | **Rejected** — no download right. Best diagnostic fit of all; worth asking permission. Manifest: `kix-dnd-amateurs-first-session` |
| Amateur Hour, *D&D Edition Ep 1* — [`3Mv7fuK_NJI`](https://www.youtube.com/watch?v=3Mv7fuK_NJI) | 1:25:50 | Standard YouTube — no Creative Commons row in the page markup, and `yt-dlp` reports no licence field | **Rejected** — no download right, and at 1 h 26 m it fills no gap the corpus has, so it gets no manifest of its own |
| Oxventure *Wyrdwood* ch. 1–4 — [`H39LNrL_VH0`](https://www.youtube.com/watch?v=H39LNrL_VH0), [`uAn2kSNRLuM`](https://www.youtube.com/watch?v=uAn2kSNRLuM), [`Pu-GlIu0Gqo`](https://www.youtube.com/watch?v=Pu-GlIu0Gqo), [`rT5VwYxJbf8`](https://www.youtube.com/watch?v=rT5VwYxJbf8) | 6:30:00 across 4 files | Standard YouTube | **Rejected** — no download right; commercial rights holder. Also would not have tested single-file duration. Manifest: `oxventure-wyrdwood-campaign` |
| SIR HORSE, *Mystic Horizon* ch. 1 ep. 1 — [`-ZzSFGgczrI`](https://www.youtube.com/watch?v=-ZzSFGgczrI) | 3:57:18, was live | **CC BY 3.0** | **Admitted** — multi-hour stress |
| Dice & Die, *Lost Mine of Phandelver* ep. 1 — [`x0vglhb46sM`](https://www.youtube.com/watch?v=x0vglhb46sM) | 2:36:57 | **CC BY 3.0** | **Admitted** — unpolished amateur |
| inwils, *Light of Xaryxis #1* — [`5EM_KEerz-k`](https://www.youtube.com/watch?v=5EM_KEerz-k) | 2:43:21 | **CC BY 3.0** — Creative Commons row present in the page markup, `yt-dlp` reports `Creative Commons Attribution license (reuse allowed)` | Not admitted — a viable third amateur item with an acceptable rights position, held back because it duplicates coverage the two admitted items already give. Admit it if either of those is withdrawn |

The goal named a product-input trigger: ask the user if no candidate with an acceptable
rights position can fill the long-form tier. One was found, so the trigger did not fire.

## A limit worth carrying forward

Neither admitted item can be byte-verified the way Hiddengrid can. YouTube re-encodes and
serves expiring URLs, so `scripts/fetch_benchmark_media.py` — which exists precisely to
make a fetch reproducible — does not apply to them. Each manifest records the digest of
the acquisition actually measured, and says plainly that a second person will re-derive
the duration but not necessarily the bytes.

That is an argument for preferring sources published as direct files. Hiddengrid's value
is not only its licence; it is that the project can prove it is holding the same bytes the
truth was anchored in.
