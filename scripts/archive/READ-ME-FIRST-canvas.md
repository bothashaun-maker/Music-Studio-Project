# 🎛️ Song Timestamp Studio — ComfyUI canvas — READ ME FIRST

**v2.0 — big-song upload fix.** The little "choose file to upload" button on the old
node 1 died on big songs over the Cloudflare link (*Upload failed: Fetch timeout*) —
songs are huge next to video frames, and the server capped uploads at 100 MB. v2.0
replaces it with a chunked, resumable uploader + link box + Kaggle import. **If you
imported the older canvas notebook, delete it and import this one.**

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
2. **Get your song in** — the cell prints a second link: **📤 Upload songs**. Open it
   once per song:
   - **Drop the song file** (WAV / FLAC / MP3, up to 2 GB) — you get a progress bar;
     it sends the song in small pieces with automatic retries, so a slow link cannot
     kill it. Keep the tab open until 100%.
   - or paste a **link** — the Kaggle machine downloads it at full speed.
   - or press **Import** for a song already on Kaggle (YuE2 render from the same
     session, or added with **+ Add Input**).
   The song appears in the **1 · Your song** list by itself — pick it there.
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
| 1 | Your Song | pick from the list · paste a link · 📤 upload (big-file safe) |
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
| **Upload failed: Fetch timeout** | That was the old single-shot button — it's gone in v2.0. Use the **📤 Upload songs** link: pieces + auto-retry + progress bar. Finished pieces are kept, so re-picking the file continues where it stopped. |
| Upload stuck | keep the tab open; it retries itself. If the internet dropped completely, pick the file again. |
| Song over 100 MB | fine — up to 2 GB (the server limit was raised from 100 MB). |
| New song not in the list | the canvas tab refreshes by itself; if not, reload the canvas tab (F5). |
| First Run slow | Whisper models are pre-cached by the setup cell; otherwise one download (~150–500 MB). |
| 🔴 Low match % | model `small`; vocal isolation ON; check Language. |
| All times early/late | Nudge node → offset → Run again. |
| No chapters | add `[Verse]` / `[Chorus]` tags to the lyrics. |
| REAPER CSV won't import | drag into the Region/Marker Manager window, not the timeline. |
| Link dead | links live only while the Kaggle session runs — re-run the cell. |
| Port 8188 busy | one notebook setup at a time per session. |

*Timestamp Studio canvas v2.0 — works on any song, not just YuE2 renders.*
