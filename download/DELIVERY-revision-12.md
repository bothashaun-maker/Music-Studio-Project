# Music Revision 12 — one cell, canvas first (+ Timestamp Studio canvas)

## What you asked for

"**I want all my music workflows to work exactly the same as the movies. The music
creation and the time stamp studio.**" — no more AIQUEST-style multi-cell notebook:
one cell, one Cloudflare link, real ComfyUI canvases, exactly like your H3 Director.

## What changed

### 1 · `yue2-3b-frontier-full-song-music-generation.ipynb` — Revision 12
- **Was:** 5 separate cells (payload → Gradio → ComfyUI → find-song → recovery) — the
  old "AIQUEST wrapper" layout.
- **Now:** **ONE executable cell** (md + code + md, like your Director notebook):
  setup → weight verification → pinned ComfyUI v0.43.2 + KaggleYuE2 pack → persistent
  server → prints ☁️ Cloudflare links that **open the Full Song / Cover canvases
  directly** (`?yue2_workflow=song|cover`). Canvases pre-installed in **Workflows**.
- The original Gradio generator is still inside: set `GRADIO_UI = True` at the top of
  the cell and run again — the engine lock hands over automatically (unchanged behaviour).
- Saved-song listing now prints in the cell; the decode-recovery snippet is documented
  in the closing markdown (paste only if ever needed). No auto-render, no download prompts.
- Sources unchanged: same engine, same node pack, same canvases, same saved-run format.

### 2 · `Song-Timestamp-Studio-Canvas.ipynb` — NEW (the timestamp app, Movies-style)
- The Gradio web app is replaced by a real **7-node ComfyUI canvas** (TimestampStudio pack):
  `LoadAudio → Align Lyrics ← Lyrics & Options`, with `Nudge All Timestamps → Export All
  Formats + ZIP` and `Audition One Line → PreviewAudio` branches.
- Same tested engine underneath (forced alignment of your known lyrics + librosa beats).
- One cell → persistent ComfyUI (CPU-friendly, Accelerator None) → ☁️ Cloudflare link with
  `?sts_workflow=studio` opens the graph directly. Whisper base+small models pre-cached
  during setup so the first Run is instant.
- Export All writes 8 formats + one ZIP into `timestamp_studio/<song>_timestamps/`
  under Kaggle Output, with a per-line confidence report.

## Validation (no Kaggle GPU used)

| Check | Result |
|---|---|
| Music repo test suite | **77/77 pass** (incl. 5 new STS structure/format tests; single-cell shape asserted) |
| STS canvas end-to-end in real pinned ComfyUI (CPU) | queued via the real `/prompt` API: all 5 nodes executed, all 9 export files + ZIP written |
| Accuracy through the CANVAS node path | per-line error **−0.22 / +0.28 / +0.34 / +0.46 / +0.33 / 0.00 s** vs ground truth — identical to the standalone engine (max ±0.46 s) |
| Nudge through the canvas | +3.2 s shifted every line by exactly +3.20 s |
| REAPER CSV / Cut Plan from the canvas | markers + regions present; frames @ 24 fps column present |
| Browser audit (real Chromium) | `?sts_workflow=studio` auto-loads all 7 nodes, no page errors, link parameter stripped, refresh preserves the graph (screenshot in `timestamp-studio-screens/`) |
| Cloudflare link itself | same checksummed `cloudflared` helper as YuE2/H3; live-tested earlier today (served the app through a real `…trycloudflare.com` URL) |
| LRC format fix | sung lines no longer wrapped in `[brackets]` (tags keep them) — standard LRC |

**Not yet verified:** a real Kaggle T4 render of either notebook (they need your
session) — CPU/browser checks cannot promise GPU behaviour. The YuE2 single-cell
launch code is the same logic validated in revision 11's cell, restructured.

## What to upload to GitHub (replaces the revision 11 task)

Upload the **contents of `yue2-music-revision-12.zip` (35 files)** to
`bothashaun-maker/Music` via GitHub's web UI (Add file → Upload files), plus
`Song-Timestamp-Studio-Canvas.ipynb`. Then reply **"done"**.

## Files

| File | What |
|---|---|
| `yue2-music-revision-12.zip` | full Music repo source (35 files) |
| `yue2-3b-frontier-full-song-music-generation.ipynb` | the R12 notebook on its own |
| `Song-Timestamp-Studio-Canvas.zip` | 👈 the timestamp app (notebook + READ ME FIRST) |
| `Song-Timestamp-Studio-Canvas.ipynb` | the canvas notebook on its own |
| `timestamp-studio-screens/canvas_loaded.png` | the canvas opened in a real browser |
