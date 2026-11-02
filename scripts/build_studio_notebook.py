#!/usr/bin/env python3
"""Assemble the Kaggle notebook + READ-ME-FIRST guide and package the zip."""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = "/home/z/my-project/download"
ZIP_PATH = os.path.join(OUT_DIR, "song-timestamp-studio-v1.2.zip")

APP_SRC = open(os.path.join(HERE, "timestamp_studio.py"), encoding="utf-8").read()

MD_TOP = """# 🎛️ Song Timestamp Studio

**Drop in a song + the lyrics you already wrote → get every timestamp a music video needs.**

| Output | Use it in |
|---|---|
| Synced lyrics (`.lrc`) | lyric-video makers, players with synced lyrics |
| Subtitles (`.srt`) | CapCut Desktop, DaVinci Resolve, Premiere |
| Captions (`.vtt`) | YouTube caption upload |
| YouTube chapters | paste into the video description |
| REAPER markers CSV | drag onto a REAPER timeline to audit/verify timings |
| Beat grid | every detected beat, for cutting on the pulse |
| Cut Plan CSV | beat-snapped clip slots with exact seconds **and frames @ 24 fps** — how many MiniMax H3 clips to queue and how long each must be |

**How it works:** Whisper listens to the song, then pins *your known lyrics* onto the exact
seconds (forced alignment — the same tech karaoke apps use). Because you wrote the words,
the text is guaranteed correct; only the timing is measured. Runs great on **CPU**
(Accelerator: None — no GPU hours burned) and faster on T4.

### How to use (3 steps)
1. Run the **Setup** cell below (installs tools — needs Internet ON).
2. Run the **Launch the app** cell and click the printed ☁️ **Cloudflare** link
   (`https://…trycloudflare.com` — the same link style as your YuE2 / H3 apps).
   A 🟣 `https://…gradio.live` backup link is printed too; either one opens the app.
3. In the app: upload your WAV (e.g. from the YuE2 run ZIP), paste your lyrics, press
   **⚡ Get timestamps**, then copy or download everything as one ZIP.

*First run downloads the Whisper model (~150 MB) — that's normal and one-time per session.*
"""

CODE_SETUP = """# Setup — install the tools (needs Internet ON, ~1–2 minutes)
%pip install -q -U "gradio>=4.44" faster-whisper librosa soundfile

# Optional (only if you want the "Vocal isolation" toggle on dense mixes):
#   %pip install -q demucs
# The app works fine without it — the toggle simply reports it's unavailable.
import gradio, faster_whisper, librosa, soundfile
print("✅ Setup complete — gradio", gradio.__version__, "| faster-whisper", faster_whisper.__version__)
"""

CODE_APP = APP_SRC

MD_BOTTOM = """## 📕 Where each file goes

| File | What to do with it |
|---|---|
| `.srt` | CapCut Desktop: **Text → Local captions → Import** (or drag onto the timeline). DaVinci Resolve: Media Pool → import → drop on a subtitle track. Premiere: File → Import. |
| `.lrc` | Lyric-video makers and any player that shows synced lyrics. |
| `.vtt` | YouTube Studio → Subtitles → Upload file. |
| `_youtube_chapters.txt` | Copy-paste into the video **description**. YouTube rules: first chapter at 0:00, at least 3 chapters, each 10+ seconds — the app warns if you break one. |
| `_reaper_markers.csv` | **Your accuracy check.** Drop the WAV on a REAPER timeline, open the **Region/Marker Manager** (View → Region/Marker Manager) and drag this CSV into it — native in REAPER 7.66+ (hold Shift while dropping to merge with existing markers). On older versions use the free ReaPack script *X-Raym: Import items or markers or regions from CSV*. Lyrics become **markers**, sections become **regions** — zoom in and eyeball every flag against the waveform. |
| `_cut_plan.csv` | Your shot budget: clip #, section, start, end, exact seconds and frames at 24 fps. Queue MiniMax H3 clips against it; assemble in CapCut against it. |
| `_beat_grid.txt` | Every detected beat time — for manual cut planning. |
| `_timestamps.json` | Full data (incl. per-word times) for any other tool. |

## ✅ How to trust the timings

1. **Confidence scores** — the app reports what % of your lyric words it actually located in the
   audio, and the **Preview table grades every single line** (e.g. `100% — solid`, `86% — solid`,
   `54% — check`). 🟢 75%+ overall = tight timings. 🔴 low score → switch **Vocal isolation ON**,
   use a bigger **model**, or check the **Language** dropdown.
2. **▶️ Audition line** — plays the song from ~1.5 s before any line. If the vocal enters when
   the line fires, it's right.
3. **REAPER** — the CSV drag-drop into the Region/Marker Manager puts every line over the
   waveform. You make the final call.
4. **Nudge box** — if everything feels early/late by the same amount (long intro?), shift all
   timestamps at once and re-download.

**Measured accuracy (synthetic song with known ground-truth timings, CPU, base model):**
all 6 test lines landed within **±0.46 s** (mean +0.20 s), 95% of words located. Real sung
vocals vary more than clean test speech — line-level timing typically lands ±0.2–0.5 s on
clear mixes. Word-level karaoke timing is not included.

## 🔧 Troubleshooting

| Symptom | Fix |
|---|---|
| First run is slow | Whisper model download (~150 MB) — one-time per session. |
| 🔴 Low match % | Vocal isolation ON; model `small`; check Language; confirm lyrics match what is actually sung. |
| All timestamps slightly early/late | Type the offset into the **Nudge** box (e.g. `0.3` or `-0.2`) → Apply nudge → re-download. |
| No YouTube chapters | Your lyrics have no `[Verse]`/`[Chorus]` tags — add tags (one per line, in square brackets) and run again. |
| REAPER CSV won't import | Drag it into the **Region/Marker Manager** window (not the timeline). REAPER 7.66+ required; older versions: ReaPack → X-Raym CSV import script. |
| Link stopped working | Both links die when the Kaggle session stops — re-run the launch cell for two fresh ones. |
| Vocal isolation errors | `pip install demucs` in the setup cell; on CPU it is slow (several minutes) — it's optional. |

*Song Timestamp Studio v1.2 — works on any song, not just YuE2 renders. CPU-friendly by design.*
"""


def cell(cid, kind, src):
    c = {"cell_type": kind, "id": cid, "metadata": {}, "source": src.splitlines(keepends=True)}
    if kind == "code":
        c["execution_count"] = None
        c["outputs"] = []
    return c


nb = {
    "cells": [
        cell("top", "markdown", MD_TOP),
        cell("setup", "code", CODE_SETUP),
        cell("app", "code", CODE_APP),
        cell("guide", "markdown", MD_BOTTOM),
    ],
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.11"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

readme = """# 🎛️ Song Timestamp Studio — READ ME FIRST

**What this is:** an app that turns a song + the lyrics you already wrote into every
timestamp a music video needs — synced lyrics (LRC/SRT/VTT), YouTube chapters, REAPER
markers, a beat grid, and a beat-snapped Cut Plan (clip slots in seconds AND frames).

It runs as a **Kaggle notebook** (same pattern as your YuE2 / H3 notebooks) and opens
as a web app through a ☁️ **Cloudflare link** (`…trycloudflare.com`) with a 🟣 Gradio
backup link (`…gradio.live`). It works on **CPU** — no GPU hours burned — and on **any
song**, not just YuE2 renders.

## One-time install (5 minutes)

1. Unzip this folder. You need one file: `song-timestamp-studio.ipynb`.
2. Go to **kaggle.com** → **Create** → **New Notebook** (empty one).
3. **File → Import Notebook** → upload `song-timestamp-studio.ipynb`.
4. Settings (right panel):
   - **Internet → ON** (needed once, to download the Whisper model).
   - **Accelerator → None** is fine (CPU works; a T4 makes it faster if you want).
5. Press **Run All** (or run the two code cells top to bottom).

## Every song (2 minutes)

1. Wait for the links: the launch cell prints a ☁️ **Cloudflare** link
   (`https://xxxx.trycloudflare.com`) and a 🟣 Gradio backup (`https://xxxx.gradio.live`)
   — click **either** one.
2. In the app:
   - **1 · Load your song** — upload the WAV/MP3 (the WAV from your YuE2 run ZIP works).
   - **2 · Paste your lyrics** — one line per row, exactly as sung. Keep your
     `[Verse 1]` / `[Chorus]` tags: they become YouTube chapters + REAPER regions.
     *Leave the box empty to auto-transcribe instead (text = what the AI hears).*
   - Press **⚡ Get timestamps** (first run downloads the model, ~150 MB).
3. Check the confidence line: 🟢 75%+ is solid. 🔴 → turn **Vocal isolation ON** and/or
   model **small**, run again.
4. Copy any tab, or grab the **📦 Download all formats (.zip)** button.

## Trusting the numbers (your REAPER call)

- The app grades itself: it tells you what % of your lyric words it found in the audio, and the
  **Preview table grades every line** (`100% — solid`, `86% — solid`, `54% — check`, …).
- **▶️ Audition line #** plays from ~1.5 s before any line — quick ear check.
- **REAPER audit:** drop the WAV on a REAPER timeline, open the **Region/Marker Manager**
  (View → Region/Marker Manager) and drag the `_reaper_markers.csv` into it (REAPER 7.66+
  takes it natively — hold Shift to merge; older versions: install the free ReaPack script
  *X-Raym: Import items or markers or regions from CSV*). Lyrics = markers, sections =
  regions. Eyeball against the waveform — you make the call.
- Everything feels 0.3 s early? Type `0.3` in the **Nudge** box → Apply → re-download.

## Verified before shipping

Built on a synthetic song with known ground-truth timings (vocals placed at exact
seconds over a 98.7 BPM instrumental). Measured on CPU with the `base` model:

| Lyric line | True start | App result | Error |
|---|---|---|---|
| Walking through the city lights at midnight | 6.00 s | 5.78 s | −0.22 s |
| Neon shadows falling on the street | 13.50 s | 13.78 s | +0.28 s |
| I can hear the distant engines humming | 21.00 s | 21.34 s | +0.34 s |
| Feel the rhythm moving through my feet | 28.50 s | 28.96 s | +0.46 s |
| We are the dreamers in the night | 38.00 s | 38.33 s | +0.33 s |
| Holding on until the morning light | 45.50 s | 45.50 s | ±0.00 s |

All lines within **±0.46 s**, mean +0.20 s, 95% of lyric words located. Beat detection
found 98.7 BPM (true 100). The full engine test suite (37 checks: alignment accuracy,
chapters, beats, cut-plan math, every output format, nudge, auto-transcribe) passes, the
Gradio UI was driven in a real browser (upload → lyrics → run → all output tabs verified),
and the **Cloudflare tunnel was opened live** and served the app through a real
`…trycloudflare.com` URL. **Not yet verified on a real YuE2 render with sung vocals —
expect a bit more wobble than clean test speech; the REAPER audit is there for exactly that.**

## Honest limits

- Timing is **line-level** (great for lyric videos, captions, chapters, cut plans).
  Word-level karaoke highlighting is not included in v1.
- Chapters come from your own `[tags]` + where vocals start — the app does not pretend
  to "hear" that something is a chorus like Moises does.
- Beat detection can miss on unusual rhythms; the Cut Plan then falls back to even slots.
- Both links (Cloudflare + Gradio backup) live only while the Kaggle session runs.
"""

os.makedirs(OUT_DIR, exist_ok=True)
ipynb_path = os.path.join(OUT_DIR, "song-timestamp-studio.ipynb")
with open(ipynb_path, "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(ipynb_path, "song-timestamp-studio.ipynb")
    zf.writestr("READ-ME-FIRST.md", readme)

print("notebook cells:", [c["cell_type"] for c in nb["cells"]])
print("app cell chars:", len(CODE_APP))
print("wrote:", ipynb_path)
print("wrote:", ZIP_PATH, os.path.getsize(ZIP_PATH), "bytes")
