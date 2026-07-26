# Window transcripts

**These are uncorrected machine drafts. They are not a reference transcript, and computing a
word error rate against them measures agreement with `large-v3-turbo` rather than accuracy.**

Every file says so in its own `status` and `usable_for_word_error_rate` fields, so a program
can refuse them instead of relying on someone having read this page.

## Why they are here at all

The project cannot measure transcription accuracy against anything, because no reference
exists. `mystic-horizon-ch1ep1-killing-zombozos` is the first source whose licence permits one
to be committed: CC BY 3.0 allows attributed redistribution of derivatives, which every other
candidate's licence does not.

What is missing is a person. A reference transcript is a human-corrected transcript by
definition, and the annotator that produced these drafts has no ears. So the drafts are
committed at the stage they actually reached, with the remaining step named, rather than
promoted to something they are not:

| Stage | Status |
|---|---|
| Windows chosen on measurement | done — justified in [`../notes/mystic-horizon-ch1ep1-annotation.md`](../notes/mystic-horizon-ch1ep1-annotation.md) |
| Decoded twice, by different implementations and model families | done |
| Disagreements located and flagged for a listener | done |
| **Corrected by a person** | **not done** |

Until the last row is done these are drafts. When it is done, the corrected text replaces
`primary`, `status` changes, and the correction method goes in the file — because a corrector
reads what is written more readily than what was said, and how the correction was performed
bounds what the result means.

## What is in a file

```json
{
  "manifest_id": "...",
  "window": {"start_ms": 60000, "end_ms": 240000, "label": "W1"},
  "status": "uncorrected_machine_draft",
  "usable_for_word_error_rate": false,
  "identity": {"...": "which recording these offsets are into"},
  "attribution": {"...": "CC BY 3.0, see below"},
  "producers": ["whisper.cpp large-v3-turbo (beam 5)", "openai-whisper medium.en"],
  "agreement": {"...": "window-level, see below"},
  "segments": [
    {
      "start_ms": 60000,
      "end_ms": 64560,
      "primary": "what the primary engine produced",
      "secondary": "what the second engine produced over the same span",
      "secondary_support": 0.83,
      "words": 13
    }
  ]
}
```

A segment that straddles a window boundary is included whole, so the first and last
`start_ms`/`end_ms` can fall a little outside `window`. Truncating a machine segment's text at
a time boundary would produce a line neither engine produced, which is worse than a few seconds
of overhang.

`primary` and `secondary` are kept apart rather than merged. Merging them would invent a
third transcript neither engine produced and hide exactly the information a corrector needs.

`secondary_support` is the share of this segment's `primary` words that survive a token-level
alignment against the second engine's text. The alignment is computed over the **whole window**
and then attributed back to segments, so the two engines splitting the same speech into
different segments does not read as disagreement — which it did in the first version of this,
and which halved every number.

It is a triage signal, not a quality score. Low support means a listener should hear that
segment. High support means both engines produced the same words, which is not the same as
their being the right words: two engines from the same lineage share failure modes, and this
pair produced three different wrong spellings of one character name in this very recording.

The window-level `agreement` block is the number to read first, and it says something the
per-segment figures do not. Across the three windows, 87–93% of the *second* engine's words are
found in the first engine's, while the first produces up to 41% more words than the second. The
disagreement is overwhelmingly **omission, not contradiction** — `medium.en` hears less, rather
than hearing differently. So agreement between these two is a weaker check than it sounds.

## Offsets are into a particular recording

`start_ms` and `end_ms` are offsets into the same recording the manifest anchors are into, and
this source does not serve the same bytes twice. Before trusting them against a copy you
obtained yourself:

```bash
uv run python scripts/audio_identity.py verify <your-audio-file> \
  --against benchmarks/fingerprints/mystic-horizon-ch1ep1-killing-zombozos.json
```

Apply any offset it reports to every timestamp in these files. The procedure and its
demonstration are in [`../notes/recording-identity.md`](../notes/recording-identity.md).

## Correcting one

[`mystic-horizon-ch1ep1-killing-zombozos/correction-worksheet.md`](mystic-horizon-ch1ep1-killing-zombozos/correction-worksheet.md)
is built to be listened to **without** reading the drafts first. It gives spans and no machine
text.

That is deliberate and it is the more important half of this directory. B02 asked a listener to
adjudicate a contested word after telling him the hypothesis, and his report came back matching
a sentence two seconds away — the priming did not just bias the answer, it moved which sentence
he answered about. The Hiddengrid manifest now records that token twice, once per listening,
with the priming stated both times. A corrector who reads a draft before listening is primed by
every line of it.

## Attribution

Required by CC BY 3.0, and the reason these files may be committed:

> Derived from **D&D: Mystic Horizon | Ch. 1 Ep. 1 | Killing Zombozos** by **SIR HORSE**,
> <https://www.youtube.com/watch?v=-ZzSFGgczrI>, licensed
> [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
> Licence read from the watch page markup on 2026-07-26 and independently reported by `yt-dlp`
> as `Creative Commons Attribution license (reuse allowed)`.
> **Modified**: three windows totalling nine minutes were machine-transcribed by two engines;
> the transcripts are excerpts and are not the complete work.

Each file repeats this in its `attribution` object, because a file gets copied out of its
directory and the licence obligation travels with the file.

Two limits on that grant, unchanged from the manifest's rights review. The uploader can only
license what the uploader owns, so Dungeons & Dragons material remains Wizards of the Coast's.
And the licence covers the content, not the route by which a copy is obtained, which is
separately subject to the platform's terms.

## What does not go in here

The full four-hour transcript. Repository policy keeps recordings and full transcripts out of
Git regardless of licence, and the goal that authorised these files authorised them **only for
the windows annotated**. Nine minutes of 237 is the whole point of choosing windows; committing
the rest would discard the constraint and the reason for it.
