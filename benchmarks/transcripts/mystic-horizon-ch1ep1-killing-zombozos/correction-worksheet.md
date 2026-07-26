# Correction worksheet

**Do not read the draft files in this directory before you finish this worksheet.**

That is the whole design. Every line of `w1-00-01-00.json`, `w2-00-40-00.json` and
`w3-03-49-00.json` is a machine's guess, and reading one before listening makes you check
whether the guess sounds right instead of hearing what was said. This project has already
watched that happen: a listener asked to adjudicate a contested word, having been told the
hypothesis first, came back with a sentence from two seconds away. It is recorded in
`benchmarks/manifests/hiddengrid-swc-ep044-tower-play.json`, twice, because it happened twice.

You are the only source of information here that is not derived from `large-v3-turbo`.

## Before you start: is your copy the right recording?

These timecodes are offsets into a recording, and this source hands out a different file to
every downloader. Check first, and it takes one command:

```bash
uv run python scripts/audio_identity.py verify <your-audio-file> \
  --against benchmarks/fingerprints/mystic-horizon-ch1ep1-killing-zombozos.json
```

If it prints an offset, **add that offset to every timecode below, sign included**. It is
usually well under a second. If it says DIFFERENT RECORDING, stop — you have another video and
nothing here applies; if it says TOO SHORT TO JUDGE, you have an excerpt rather than the full
recording.

## Task A — one window, transcribed blind

**Window W1: `00:01:00` to `00:04:00`.** Three minutes. Play it and write what you hear.

This is the task that produces something the project does not have: a reference transcript
with a person behind it. Everything else on this page is triage.

Some conventions, so the result can be scored later:

- Write words, not timecodes. Start a new line whenever the speaker changes.
- If you cannot tell who is speaking, that is fine and expected — this is a single mixed
  track. Leave the speaker unlabelled rather than guessing.
- Mark anything you genuinely cannot make out as `[unclear]`. An honest `[unclear]` is worth
  more than a plausible guess, because a guess becomes truth once it is committed.
- Keep false starts, "um", and repeated words. They are what the audio contains, and a
  transcript that tidies them up cannot measure a transcriber that does not.
- Do not correct grammar, and do not resolve names into spellings you think are right. Write
  what it sounds like. Spelling is settled from written sources afterwards, separately, and
  the manifest records which of the two did the work for each name.

W1 was picked as the recording's **best case**: the highest ASR coverage and the lowest quiet
fraction anywhere in the four hours. So whatever accuracy you find here is the ceiling, not
the average.

## Task B — passages where the two engines went different ways

145 seconds in total. These are spans where the second engine failed to support more than half
of what the first produced.

You are told the spans and not the readings. That is the least priming that still lets you
find them; knowing a passage is contested is unavoidable, knowing what it is contested
*between* is not.

For each, play it and write what you hear.

### W1 — 8 passages, 97 s

| Span | Length | What you hear |
|---|---|---|
| `00:00:53` – `00:01:03` | 10 s |  |
| `00:01:14` – `00:01:31` | 17 s |  |
| `00:01:37` – `00:01:57` | 20 s |  |
| `00:02:00` – `00:02:17` | 17 s |  |
| `00:02:35` – `00:02:42` | 7 s |  |
| `00:03:08` – `00:03:15` | 7 s |  |
| `00:03:42` – `00:03:51` | 9 s |  |
| `00:03:55` – `00:04:06` | 11 s |  |

(These fall inside Task A. If you do Task A first, they are already answered — do Task B only
if you skip Task A.)

### W2 — 3 passages, 36 s

| Span | Length | What you hear |
|---|---|---|
| `00:40:54` – `00:41:06` | 12 s |  |
| `00:41:39` – `00:41:45` | 6 s |  |
| `00:42:45` – `00:43:02` | 18 s |  |

### W3 — 1 passage, 12 s

| Span | Length | What you hear |
|---|---|---|
| `03:49:30` – `03:49:42` | 12 s |  |

## Task C — one open question, and it is not about a word

Play **`00:01:50` to `00:02:10`** and **`00:36:35` to `00:36:50`**.

A name is spoken in both. Both engines write it the same way. It is not in the publisher's
cast list, which credits five people and gives each a character, so the corpus has no written
source for it at all — the same position `Freya` is in on the Hiddengrid item.

Two things would help, and neither requires deciding a spelling:

1. Does it sound like a nickname being used for one of the people credited, or like a sixth
   person the credits leave out?
2. Is the same voice speaking as the one addressed at `00:09:35`?

If you cannot tell, say so. "Cannot tell from the audio" is the answer that stops a guess
becoming a manifest entry, and it is the answer the corpus is short of.

## What happens to what you write

- Task A replaces `primary` in `w1-00-01-00.json`, `status` becomes corrected, and the file
  records how the correction was done — including that the corrector worked from audio and not
  from the draft, which is the claim this worksheet exists to make true.
- Task B updates the affected segments in W2 and W3 only. Those two files stay drafts, because
  a spot-corrected transcript is not a reference and calling it one would be the exact
  overclaim this corpus is built to avoid.
- Task C goes into the manifest's evidence for that entity, worded as what you reported and
  not as what it establishes.

Nothing you write is scored, and there is no wrong answer that costs anything. The failure
mode here is a confident answer, not a missing one.
