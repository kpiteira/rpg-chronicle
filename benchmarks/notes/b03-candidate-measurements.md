# Acoustic measurements: the B03 candidates

Raw output behind the `recording_conditions` blocks of
[`../manifests/mystic-horizon-ch1ep1-killing-zombozos.json`](../manifests/mystic-horizon-ch1ep1-killing-zombozos.json)
and
[`../manifests/dice-and-die-lmop-e01-stranger-danger.json`](../manifests/dice-and-die-lmop-e01-stranger-danger.json),
following the pattern B02 set for Hiddengrid.

Recorded 2026-07-26. These are measurements — durations, levels, pause counts — not audio
and not content. They are committed so a reader can check the manifests' acoustic claims
without repeating the acquisition, which matters more here than for Hiddengrid: **these
two cannot be byte-reproduced.** YouTube re-encodes and serves expiring URLs, so a second
person re-derives the duration but not necessarily the digest below. That is the reason to
commit the numbers rather than only the recipe.

The two rejected candidates have no measurements at all, by design: they were ruled out on
rights before anything was acquired.

## Acquisition

Both items are CC BY 3.0, which is what permits processing a copy at all:

```bash
yt-dlp -f 140 -o mystic_ch1ep1.%(ext)s https://www.youtube.com/watch?v=-ZzSFGgczrI
yt-dlp -f 140 -o dicedie_e01.%(ext)s   https://www.youtube.com/watch?v=x0vglhb46sM
```

Format 140 is AAC-LC 128 kbit/s at 44.1 kHz — YouTube's audio-only stream, already a
re-encode of whatever the creators uploaded. Nothing below describes the original capture;
it describes what the platform serves.

## Commands

```bash
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels,bit_rate \
                 -show_entries format=duration -of default=nw=1 $F
ffmpeg -i $F -af astats -f null -                                  # per-channel levels
ffmpeg -i $F -af "pan=mono|c0=0.5*c0-0.5*c1,astats" -f null -      # L-R residual
ffmpeg -i $F -af ebur128=peak=true -f null -                       # loudness
ffmpeg -i $F -af "highpass=f=12000,astats" -f null -               # band energy
ffmpeg -i $F -af "silencedetect=noise=-40dB:d=0.5" -f null -       # gaps
```

The music determinations are the one figure below that is read off a picture rather than a
number, so the commands that produced those pictures are here too:

```bash
# Dice & Die: intro bed, visible as a dense broadband block at 00:00:10-00:00:31
ffmpeg -t 240 -i dicedie_e01.m4a \
  -lavfi "showspectrumpic=s=1200x400:mode=combined:legend=1:scale=log" dicedie_e01_spec.png

# Mystic Horizon: the five sampled windows, none of which showed music
ffmpeg -t 240 -i mystic_ch1ep1.m4a -lavfi "showspectrumpic=..." mystic_spec.png
for T in 3600 7200 10800 14100; do
  ffmpeg -ss $T -t 90 -i mystic_ch1ep1.m4a \
    -lavfi "showspectrumpic=s=900x300:mode=combined:legend=0:scale=log" mystic_at_$T.png
done
```

Speech shows as vertical striations with gaps between them; a music bed shows as sustained
horizontal bands. Ten minutes of a 3 h 57 m file is a sample, not an inspection, which is
why that manifest says `null` and not `false`.

## Output

```text
### mystic_ch1ep1.m4a
  sha256  83999e0cb827ac2243bdc097b5097c2e990b9cf5a00c4e02f31e0332cd20af7f
  bytes   230265075
  codec_name=aac
  sample_rate=44100
  channels=2
  bit_rate=127999
  duration=14238.058231
    Channel: 1
    Peak level dB: 0.118460
    RMS level dB: -20.690620
    Channel: 2
    Peak level dB: 0.176707
    RMS level dB: -20.690492
  L-R residual RMS level dB: -55.220061

### dicedie_e01.m4a
  sha256  43f2768e60db6b5a4fd67d94c881d50d4513677d7614c78e553e60b68211dcba
  bytes   152299342
  codec_name=aac
  sample_rate=44100
  channels=2
  bit_rate=127999
  duration=9417.177687
    Channel: 1
    Peak level dB: 1.285601
    RMS level dB: -22.735964
    Channel: 2
    Peak level dB: 1.285601
    RMS level dB: -22.735894
  L-R residual RMS level dB: -75.409813

=== mystic_ch1ep1 ebur128 ===
    I:         -14.6 LUFS
    LRA:        17.1 LU
    Peak:        0.7 dBFS
=== mystic_ch1ep1 band energy (full vs >12kHz) ===
  full  [Parsed_astats_0 @ 0x907048900] RMS level dB: -20.690620
  >12k  [Parsed_astats_1 @ 0x9b50349c0] RMS level dB: -46.959520
=== mystic_ch1ep1 silence structure ===
  gaps >0.5s at -40dB: 3285
=== dicedie_e01 ebur128 ===
    I:         -17.2 LUFS
    LRA:        15.8 LU
    Peak:        2.2 dBFS
=== dicedie_e01 band energy (full vs >12kHz) ===
  full  [Parsed_astats_0 @ 0x82503c900] RMS level dB: -22.735964
  >12k  [Parsed_astats_1 @ 0x7f103c9c0] RMS level dB: -47.339767
=== dicedie_e01 silence structure ===
  gaps >0.5s at -40dB: 1874
```

## What the numbers mean

**Neither item has a per-speaker channel.** The L−R residuals sit 34 dB (Mystic Horizon)
and 53 dB (Dice & Die) below programme, so both are single mixed tracks — the Dice & Die
figure is a duplicated mono source. Diarization probed on either works from one signal.

**Both are unpolished in a way nothing else in the corpus is.** Loudness ranges of 17.1 LU
and 15.8 LU against Hiddengrid's post-levelled 8.2 LU, with true peaks of +0.7 and
+2.2 dBFS — both clipping. This is the property they were admitted for.

**Turn-taking is dense in both**: about 14 gaps per minute over Mystic Horizon's four
hours, about 12 over Dice & Die's two and a half. Neither is monologue.

**Music was sampled, not settled, on Mystic Horizon.** Five windows totalling about ten
minutes of a 3 h 57 m file — 0–4 min, then 90 s each at 1 h, 2 h, 3 h and 3 h 55 m — showed
speech and no music, which is why the manifest records `music_or_effects: null` rather than
`false`. Dice & Die is `true` on a directly observed intro bed at 00:00:10–00:00:31.
