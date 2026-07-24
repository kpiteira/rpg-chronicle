# B01 benchmark candidates and R0 recommendation

Access review: 2026-07-24.

## Outcome

Recommend Hiddengrid Episode 044 as the first real R0 input, subject to the
NoDerivatives handling constraints below. Retain Critical Role C3E1 as a polished
comparison candidate, not an automated-fetch input.

This pair is deliberately small. It spans corpus tiers 1 and 2 and separates a modern
professional studio baseline from an older independent podcast whose capture topology,
speaker count, overlap, and truth need discovery. Neither represents tier 3
single-room/iPad audio; that gap remains explicit rather than being inferred from a
podcast's sound.

## Candidate evidence

### Critical Role C3E1 — alternate

- The [official recap](https://critrole.com/critical-recap-critical-role-c3e1-the-draw-of-destiny/)
  identifies Jrusar, Imogen, and Laudna and links the official Critical Role YouTube
  channel.
- The [Omen Archive timestamp index](https://www.omenarchive.com/c3/e1/) places the
  episode start at `00:13:05`, Imogen's introduction at `00:18:10`, and Laudna's at
  `00:19:10`. The manifest selects `00:13:05–00:20:30`.
- A header check on 2026-07-24 returned HTTP 200 for
  `https://www.youtube.com/watch?v=P8pLvV3FjPc`.
- Public metadata reports a 3:58:24 runtime and nine physical participants. These are
  navigation aids, not reference annotations.
- No permission to download, transform, or redistribute the episode for this benchmark
  was identified. The manifest therefore marks local processing `unknown` and
  redistribution `restricted`. B02 must not automate acquisition unless that changes.

Diagnostic value: clean close-mic speech, dense invented geography, narrated exposition,
and sequential character introductions provide a useful upper-bound baseline.

### Hiddengrid Episode 044 — recommended

- The [publisher archive](https://www.hiddengrid.com/) describes The Sixth World
  Chronicles as a Shadowrun actual-play podcast and records both Topps's ownership of
  Shadowrun material and a CC BY-NC-ND 4.0 license for Hiddengrid.
- The [podcast archive index](https://audiofiction.co.uk/show.php?id=20130201-01)
  identifies Episode 044 as “Maria Mercurial – Session 6 – Tower Play” and exposes the
  publisher-hosted MP3 URL.
- A fresh 2026-07-24 fetch returned HTTP 200, `audio/mpeg`, 127,266,240 bytes, duration
  7,954.009375 seconds, and SHA-256
  `2a0f5272568b772fe9bcfd9371231484b153dc79e755564490a69b2552ac37e9`.
  The manifest's `00:00:00–00:10:00` window is therefore valid. The downloaded file was
  kept outside Git in `/tmp`.
- The [license deed](https://creativecommons.org/licenses/by-nc-nd/4.0/) permits sharing
  the unadapted material with attribution for noncommercial purposes, but prohibits
  distributing adapted material. It does not erase third-party rights.

Diagnostic value: an older independent full-cast recording without a public transcript
tests discovery, diarization, and fantasy/cyberpunk-name handling under less controlled
conditions.

## Rights and preparation guardrails

This is an engineering rights review, not legal advice.

- Keep downloaded media and generated transcripts in the private benchmark cache.
- Attribute Hiddengrid and link the license in run metadata.
- Process the original Hiddengrid file and apply the excerpt as a logical time window.
  Do not publish a clipped, denoised, reformatted, transcribed, or otherwise adapted
  artifact under the existing NoDerivatives permission.
- Do not redistribute either candidate's media from this repository.
- Treat publisher/game rights and participant privacy/publicity rights as separate from
  the podcast license.

## Truth readiness and rejected shortcuts

The committed entity/event targets are provisional source-navigation anchors, not
scoring truth. B02 should listen to the selected window and add evidence-timestamped
speaker, entity, and event annotations before any processor comparison.

Rejected:

- Treating Critical Role as downloadable merely because it is public on YouTube.
- Calling an independent podcast “single-room” without capture evidence.
- Selecting a large corpus before the first fetch, annotation, and scoring loop works.
- Publishing a ten-minute Hiddengrid clip despite the NoDerivatives restriction.

## Next step for R02/B02

B02 should implement a private-cache fetch of the original Hiddengrid MP3, verify the
recorded size/duration/checksum, and pass the logical time range to the processor. R02
can consume the stable manifest now, but should label any probe output non-comparable
until the provisional truth targets are independently annotated.
