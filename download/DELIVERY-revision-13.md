# Delivery — Music revision 13 (canvas v2.0 big-song upload fix) — 2026-11-04

## What you asked for
"Ag nee man. DO NOT SEND ME UP AND DOWN. GET THIS FIXED. YOU HAVE ONE MORE TRY."
The screenshot showed the studio canvas over Cloudflare failing with
**"Upload failed: Fetch timeout"** on the song-upload node.

## Why it broke (the honest, checked answer)
ComfyUI's built-in upload button sends the whole song as ONE request:
- ComfyUI rejects anything over **100 MB** by default (`--max-upload-size`, checked in
  the pinned source), and
- one long request over a slow Cloudflare quick-tunnel dies halfway — that is the
  "Fetch timeout" toast. Movies never showed this because video frames are tiny;
  a song WAV is 10–100× bigger.

## What v2.0 does instead
1. **Node 1 is now "Your Song"** — a list of songs already on the studio server.
2. A second printed link, **📤 Upload songs**, opens a page that sends the song in
   **8 MB pieces with auto-retry and a live progress bar** (resumable, up to **2 GB**).
3. **Paste a link** — the Kaggle machine downloads it at full speed.
4. **Import** button for songs already on Kaggle (YuE2 render, + Add Input).
5. The canvas song list updates **live** — no reload.
6. Server cap raised to 2048 MB.

## Proof (automated tests, all passing)
| Test | Result |
|---|---|
| 105 MB song in 8 MB pieces (over the old 100 MB cap) | PASS — byte-exact on server |
| Resumable (missing piece → refused 409 → retry → OK) | PASS |
| Link download / page-link refused / Kaggle import / path guard | PASS |
| **Slow-link reproduction (1.5 Mbps, 45 s kill): old path dies, new path succeeds on the same link** | **PASS** |
| Real browser: 18 MB upload → "100% (piece 3/3)" → success → song on server | PASS |
| Real browser: canvas list updates live, auto-selects the song, second song appears without reload | PASS |
| Canvas E2E through real ComfyUI queueing (max ±0.46 s, nudge exact) | PASS |
| Engine 37-check suite | PASS |

## Files
- `Song-Timestamp-Studio-Canvas.zip` ← import this one (notebook + READ-ME-FIRST)
- `Song-Timestamp-Studio-Canvas.ipynb` (same notebook, loose)
- `yue2-music-revision-13.zip` (full repo source, 35 files)
- `timestamp-studio-screens/` (uploader + canvas screenshots from the tests)

## Your steps
1. On Kaggle: **delete the old Song Timestamp Studio notebook** (so there's only one).
2. Import `Song-Timestamp-Studio-Canvas.ipynb` from the new zip.
3. Settings: **Internet ON**, **Accelerator None** is fine → **Run All**.
4. Click the ☁️ Canvas link. For each song: open the 📤 Upload songs link, drop the
   file, wait for 100%, go back to the canvas, pick the song, Run.
