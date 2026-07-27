# What real recordings do to a speech stack

Findings that shaped code, lifted out of per-recording annotation notes before those notes
moved to the content directory with the recordings they describe (`docs/CONTENT_AUDIT.md`).

Each was measured on a specific recording. The recording is not the point and is not named
here; what generalises is the property and what it forced.

## Channel imbalance is normal, so "the audio" and "channel zero" are not the same signal

An amateur single-microphone session measured **two channels differing by 34 dB**. A probe
that takes the first channel is not sampling the room, it is sampling whichever side of a
badly-balanced capture happened to be louder.

**What it forced:** the diarizer refuses multi-channel input rather than silently taking
channel zero, which an earlier probe did. Downmixing is a decision the caller makes
explicitly.

## Fantasy names defeat recognition, and two engines fail differently

A single character name produced **three different strings across two engines, none matching
the publisher's spelling**. This is not a tuning problem; the names are not in any language
model's vocabulary and the audio genuinely sounds like the wrong word.

**What it forced:** spelling and sound are recorded separately, and the source of each is
named. An engine producing the ordinary word a name is a pun on is not wrong about the
sound — it has no way to know the cast list spells it differently. The product cannot get
these right from audio alone; it needs the campaign's own vocabulary, which is what the
vault eventually supplies.

## Audio level anti-predicts recognition reliability; overlap is the thing to measure

Three windows were chosen on loudness — best case, worst case, and a late quiet stretch. The
window picked as *best* had the **worst** cross-engine agreement (0.616); the one picked as
*worst* scored 0.753, and the quiet late one scored highest at 0.868.

Speech rate tracked reliability where level did not: 146 words per minute in the worst-
agreeing window against 122 in the best.

Three points is a hypothesis, not a law. But picking on level found the hardest window by
accident and labelled it the easiest, so the practical rule is: **choose evaluation windows
on overlap and speech rate, not on loudness.**

## A real session is never silent, and 14% of it yields no words

Across four hours there was **no 1.5-second silent run anywhere**, while about 14% of the
timeline produced no words. That time is laughter, dice, breath and room — checked with a
second engine rather than assumed, and the second engine covered *less* of it, adding 19
seconds of "I", "You", "Um".

**What it forces:** silence-based segmentation has nothing to grip. A gap in recognition is
not a gap in the session, and a summary that treats unrecognised time as absence will be
wrong about a seventh of the recording.

## Off-fiction speech is unmarked and indistinguishable

A window chosen blind on acoustics landed on half a minute of a player taking a personal
phone call, mid-scene, with nothing in the audio marking it as outside the fiction.

**What it forces:** the product cannot assume everything recorded is game content. It also
means an evaluation corpus assembled from real sessions will contain private conversation
that nobody intended to publish — which is one of the reasons content lives outside this
repository rather than in it.

## Cross-engine agreement is not accuracy

Two engines agreeing establishes that neither invented a word alone. It says nothing when
both mishear the same way, and engines sharing a lineage do exactly that. Every truth target
built this way is machine-assisted and cannot be scored against the engines that produced it.

**What it forces:** basis is recorded per target — a human ear and tooling are different
things — and the providers that contributed are named so a scoring run can refuse the
combination rather than trusting that somebody read the notes.
