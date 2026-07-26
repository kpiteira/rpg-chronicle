# Acoustic measurements: Hiddengrid EP044

Raw output behind the `recording_conditions` block of
[`../manifests/hiddengrid-swc-ep044-tower-play.json`](../manifests/hiddengrid-swc-ep044-tower-play.json)
and the measurement table in
[`hiddengrid-swc-ep044-tower-play.md`](hiddengrid-swc-ep044-tower-play.md).

Recorded 2026-07-26 against the verified copy (SHA-256 `2a0f5272…ac37e9`). These are
measurements — durations, levels, and pause boundaries — not audio and not content. They
are committed so a reader can check the recording-conditions claims without re-fetching
127 MB, and so a later re-run can be compared against them.

To reproduce, fetch the media with `scripts/fetch_benchmark_media.py`, then decode it once:

```bash
ffmpeg -i <cached mp3> -ac 1 -ar 16000 -c:a pcm_s16le window.wav
```

`$MEDIA` below is the cached MP3 and `$WAV` is that decode. Anything derived from the
audio stays in the private cache; only this record is committed.

## File, channels, and band

```text
### ffprobe -v error -show_format -show_streams -of json $MEDIA
codec_name = mp3
sample_rate = 16000
channels = 2
channel_layout = stereo
bit_rate = 128000
duration = 7954.009375
format.format_name = mp3
format.duration = 7954.009375
format.size = 127266240
format.bit_rate = 128002

### ffmpeg -i $MEDIA -af astats  (per channel, whole file)
Channel: 1
Peak level dB: -0.933376
RMS level dB: -21.161696
Noise floor dB: -89.150050
Channel: 2
Peak level dB: -1.042814
RMS level dB: -21.162206
Noise floor dB: -80.346403

### ffmpeg -i $MEDIA -af 'pan=mono|c0=0.5*c0-0.5*c1,astats'  (L-R residual, whole file)
Peak level dB: -19.205531
RMS level dB: -55.417200

### ffmpeg -t 600 -i $WAV -af ebur128=peak=true  (excerpt window)
    I:         -19.2 LUFS
    Threshold: -30.7 LUFS
    LRA:         8.2 LU
    Threshold: -40.8 LUFS
    Peak:        0.2 dBFS

### band energy, speech region 120-600 s: full band vs above 7 kHz
full band  RMS level dB: -21.296954
above 7kHz RMS level dB: -47.305407
```

The two channels sit 34 dB apart (−21.2 dB programme against a −55.4 dB L−R residual), so
the delivered file is one mixed track: there is no per-speaker channel to diarize from.
Sampling at 16 kHz puts a hard ceiling at 8 kHz, and what remains above 7 kHz is 26 dB
down. Integrated loudness of −19.2 LUFS across an 8.2 LU range with a true peak of
+0.2 dBFS is a levelled, limited, produced artifact rather than a raw capture.

## Structure of the excerpt window

```bash
ffmpeg -t 600 -i $WAV -af silencedetect=noise=-40dB:d=0.5 -f null -   # gaps
ffmpeg -t 600 -i $WAV -f s16le -                                     # raw samples
```

The gap list below is that first command's output verbatim; the run lengths are its gaps
inverted, and the histogram counts samples from the second.

```text
gaps detected in 0-600 s at -40 dB, min 0.5 s: 119

continuous non-silent runs longer than 20 s (music, monologue, or laughter):
     2.88 -   57.51  ( 54.64 s)
    69.91 -  109.18  ( 39.26 s)
   402.10 -  430.09  ( 27.99 s)
   539.24 -  566.10  ( 26.86 s)

first ten gaps, which bound the opening music:
     0.00 -    2.88
    57.51 -   58.26
    61.15 -   62.19
    65.23 -   65.80
    69.00 -   69.91
   109.18 -  110.77
   111.40 -  112.00
   112.81 -  113.48
   125.80 -  126.53
   127.66 -  128.25

sample histogram over 0-600 s: 9600000 samples, 100427 exactly zero (1.05%), 440052 below |4| ~ -78 dBFS (4.58%)
```

The 54.64 s run from 00:00:03 is the theme music; the host's welcome starts over it at
about 00:00:28. The 39.26 s run from 00:01:10 is laughter and interjection over the
recap, which is what "overlap: medium" rests on. The two runs near 00:06:42 and 00:08:59
are game-master explanation, not music.

The sample histogram is the basis for calling the gaps gated: 1.05% of the window is
digital silence and 4.58% sits below roughly −78 dBFS. An open microphone in a shared
room does not produce that; it is per-speaker gating or noise suppression, which rules
out a raw single-room capture.
