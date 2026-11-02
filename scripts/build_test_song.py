#!/usr/bin/env python3
"""Build a synthetic test song with KNOWN ground-truth lyric timings.

- Instrumental bed: soft chord pad (Am F C G) + 100 BPM kick + faint noise, 56 s.
- Six TTS vocal clips placed at exact known offsets.
- Writes test_song.wav (44.1 kHz mono PCM16) + ground_truth.json.
"""
import json
import os

import numpy as np
import soundfile as sf

HERE = os.path.dirname(os.path.abspath(__file__))
CLIPS = os.path.join(HERE, "testdata", "clips")
OUT_WAV = os.path.join(HERE, "testdata", "test_song.wav")
OUT_JSON = os.path.join(HERE, "testdata", "ground_truth.json")

SR = 44100
DURATION = 56.0
KICK_BPM = 100.0
KICK_PERIOD = 60.0 / KICK_BPM  # 0.6 s

# ground-truth vocal entrances (seconds)
PLACEMENTS = [
    ("line1.wav", 6.0),
    ("line2.wav", 13.5),
    ("line3.wav", 21.0),
    ("line4.wav", 28.5),
    ("line5.wav", 38.0),
    ("line6.wav", 45.5),
]

# Am F C G - root midi notes for simple triads
CHORDS = [
    [57, 60, 64],  # A3 C4 E4
    [53, 57, 60],  # F3 A3 C4
    [48, 52, 55],  # C3 E4 G3-ish
    [55, 59, 62],  # G3 B3 D4
]
BAR = 2.0  # seconds per chord


def midi_hz(m):
    return 440.0 * 2 ** ((m - 69) / 12.0)


def build_bed():
    n = int(SR * DURATION)
    t = np.arange(n) / SR
    bed = np.zeros(n, dtype=np.float64)

    # chord pad: saw-ish sum of sines with slow attack per bar
    for bar_start in np.arange(0, DURATION, BAR):
        idx = int(bar_start / BAR) % len(CHORDS)
        s0 = int(bar_start * SR)
        s1 = min(int((bar_start + BAR) * SR), n)
        seg_t = t[s0:s1] - bar_start
        env = np.minimum(seg_t / 0.35, 1.0) * np.minimum((BAR - seg_t) / 0.5, 1.0)
        env = np.clip(env, 0, 1) * 0.05
        for m in CHORDS[idx]:
            bed[s0:s1] += env * np.sin(2 * np.pi * midi_hz(m) * seg_t)

    # kick drum: exp-decaying 55 Hz sine on every beat -> strong onsets for beat tracking
    kick_len = int(0.22 * SR)
    kt = np.arange(kick_len) / SR
    kick = np.sin(2 * np.pi * 55 * kt) * np.exp(-kt * 22) * 0.5
    for k_start in np.arange(0, DURATION - 0.3, KICK_PERIOD):
        s0 = int(k_start * SR)
        s1 = min(s0 + kick_len, n)
        bed[s0:s1] += kick[: s1 - s0]

    # faint noise floor
    bed += np.random.default_rng(7).normal(0, 0.003, n)
    return np.clip(bed, -1.0, 1.0)


def resample_linear(x, sr_in, sr_out):
    if sr_in == sr_out:
        return x.astype(np.float64)
    n_out = int(round(len(x) * sr_out / sr_in))
    t_in = np.arange(len(x)) / sr_in
    t_out = np.arange(n_out) / sr_out
    return np.interp(t_out, t_in, x)


def main():
    bed = build_bed()
    truth = {"sample_rate": SR, "duration": DURATION, "kick_bpm": KICK_BPM, "lines": []}
    for fname, start in PLACEMENTS:
        clip, sr = sf.read(os.path.join(CLIPS, fname), dtype="float64")
        if clip.ndim > 1:
            clip = clip.mean(axis=1)
        clip = resample_linear(clip, sr, SR)
        peak = np.max(np.abs(clip)) or 1.0
        clip = clip / peak * 0.85
        s0 = int(start * SR)
        s1 = min(s0 + len(clip), len(bed))
        bed[s0:s1] += clip[: s1 - s0]
        truth["lines"].append({"clip": fname, "start": start, "end": start + len(clip) / SR})
        truth["lines"][-1]["end"] = round(truth["lines"][-1]["end"], 3)

    sf.write(OUT_WAV, bed.astype(np.float32), SR, subtype="PCM_16")
    with open(OUT_JSON, "w") as f:
        json.dump(truth, f, indent=2)
    print(f"wrote {OUT_WAV}")
    for ln in truth["lines"]:
        print(f"  {ln['clip']}: {ln['start']:.2f} -> {ln['end']:.2f}")


if __name__ == "__main__":
    main()
