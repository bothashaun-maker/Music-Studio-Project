# 🎛️ Song Timestamp Studio — ComfyUI canvas — READ ME FIRST

**What this is:** your timestamp app, rebuilt **exactly like your Movies / H3 canvases**:
one Kaggle notebook with **one executable cell** → it installs everything, starts
ComfyUI, and prints a ☁️ **Cloudflare link** that opens the full **7-node canvas**
directly. No web-app wrapper. The canvas is also under ComfyUI's **Workflows** menu.

## One-time install (3 minutes)

1. Unzip. You need one file: `Song-Timestamp-Studio-Canvas.ipynb`.
2. kaggle.com → **Create → New Notebook** → **File → Import Notebook** → upload it.
3. Settings (right panel):
   - **Internet → ON** (once, for the tools + Whisper models).
   - **Accelerator → None** is perfect (CPU — no GPU hours burned; a T4 also works).
4. Press **Run All** (or run the single cell). Wait for the links.

## Every song (2 minutes)

1. Click the ☁️ **Canvas** link — the graph opens directly.
2. **LoadAudio** — upload your song (the WAV from a YuE2 run ZIP works).
3. **Lyrics & Options** — paste the lyrics exactly as sung, one line per row. Keep your
   `[Verse]` / `[Chorus]` tags → they become YouTube chapters + REAPER regions.
   *Leave it empty to auto-transcribe instead.*
4. Press **▶ Run**. **Align Lyrics** shows the match rate; **Export All** lists every
   file with a per-line confidence grade.
5. Grab everything from **Kaggle Output** → `timestamp_studio/<song>_timestamps/`
   (8 formats + one ZIP with all of it).

## The 7 nodes

| # | Node | What it does |
|---|---|---|
| 1 | LoadAudio | your song (WAV/FLAC/MP3) |
| 2 | Lyrics & Options | your words + model / language / vocal isolation |
| 3 | Align Lyrics | forced alignment — your known words onto exact seconds |
| 4 | Nudge All Timestamps | everything late/early by the same amount? shift once |
| 5 | Export All Formats + ZIP | LRC · SRT · VTT · chapters · REAPER CSV · beat grid · Cut Plan (seconds **+ frames @ 24 fps**) · JSON |
| 6 | Audition One Line | plays ~8 s around any line |
| 7 | Ear-check player | PreviewAudio for #6 |

## Trusting the numbers

1. **Per-line confidence** in the Export report (`100% — solid` / `86% — solid` / `54% — check`).
2. **▶ Audition** any line — the vocal should enter when the line fires.
3. **REAPER audit** — drop your WAV on the timeline, open **View → Region/Marker Manager**,
   drag `_reaper_markers.csv` in (REAPER 7.66+ native). Lyrics = markers, sections = regions.
4. **Nudge** — change the offset on node 4 → Run again → re-download.

**Measured on a synthetic song with known ground-truth timings (CPU, base model):**
all 6 test lines within **±0.46 s** (mean +0.20 s), 95% of words located. The same
engine passed 37 checks, and the canvas itself was queued through real ComfyUI and
reproduced those exact timings. Real sung vocals vary more — expect ±0.2–0.5 s on
clear mixes. Word-level karaoke timing is not included.

## Troubleshooting

| Symptom | Fix |
|---|---|
| First Run slow | Whisper models are pre-cached by the setup cell; otherwise one download (~150–500 MB). |
| 🔴 Low match % | model `small`; vocal isolation ON; check Language. |
| All times early/late | Nudge node → offset → Run again. |
| No chapters | add `[Verse]` / `[Chorus]` tags to the lyrics. |
| REAPER CSV won't import | drag into the Region/Marker Manager window, not the timeline. |
| Link dead | links live only while the Kaggle session runs — re-run the cell. |
| Port 8188 busy | one notebook setup at a time per session. |

*Timestamp Studio canvas v1.0 — works on any song, not just YuE2 renders.*
