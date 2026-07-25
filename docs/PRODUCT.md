# Product definition

## Problem

Long tabletop RPG sessions contain valuable story, character, location, quest, and relationship information, but manually transcribing and maintaining campaign notes takes too much time.

## User

The initial user records a roughly four-hour in-person RPG session using an iPad placed nearby. This is a personal project. Complex per-session capture rituals are not acceptable. A permanently placed table microphone and a one-time thirty-second voice enrollment per player are acceptable, because neither adds a step to game night. See `docs/CAPTURE.md`.

## Consent

Everyone at the table is told that sessions are recorded and processed, and any player may have their audio, transcript, and voice profile deleted on request. Recordings and derived campaign data stay on local storage. The capture policy is normative, not advisory.

## Core promise

Turn a minimally prepared recording into trustworthy campaign knowledge while requiring only a few minutes of targeted human review.

## North-star experience

1. A recording is imported from a configured local or network path.
2. Processing runs without manual cutting.
3. The user opens a summary-first review.
4. The system asks only high-impact unresolved questions and provides short audio evidence.
5. Corrections update the transcript, vocabulary, entities, and future context.
6. The user previews and approves campaign changes.
7. An Obsidian vault adapter applies safe, traceable updates.

## Primary metric

Human attention required to obtain a trustworthy campaign record.

Targets:

- Useful prototype: no full-transcript review.
- Personal alpha: under three minutes of review per recorded hour.
- North star: around five minutes total for a typical four-hour session.

## Supporting outcomes

- Capture at least 90% of major plot events.
- Capture at least 90% of important named entities.
- Add effectively zero important unsupported facts without warning.
- Preserve evidence linking claims to transcript turns and audio timestamps.
- Resume interrupted long-running jobs.
- Improve from approved vocabulary and speaker corrections.

## Product principles

- Summary first, transcript second.
- Ask focused questions, never assign proofreading homework.
- Automate repeatable preparation and maintenance.
- Confidence and consequence determine intervention.
- Preserve original inputs and provenance.
- Distinguish demonstrated capability from declared truth in every artifact and result.
- Separate physical speakers from fictional characters.
- Prefer a useful anonymous transcript over failed perfect diarization.
- Earn custom implementation through measured need.

## Initial non-goals

- Live transcription.
- Perfect word-for-word transcripts.
- Automatic recognition of every NPC voice.
- Per-player microphones or headsets.
- Fully autonomous destructive vault edits.
- General-purpose meeting transcription product.
