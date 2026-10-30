# YuE2 Revision 11 — ComfyUI Canvas Wrapper (delivery notes)

## What this is

Revision 11 of `bothashaun-maker/Music` adds the **ComfyUI canvas wrapper**
you asked for: after setup, a new notebook cell installs a pinned, session-only
ComfyUI v0.43.2 with the **KaggleYuE2** node pack and prints a Cloudflare link
that opens the full node graph directly — exactly like your Movies H3 canvases.
The Gradio wrapper stays as a second route; both drive the same proven FP16
engine and write the same saved-run format.

- **YuE2 Full Song canvas** — Run Context (one folder + one seed) → Load Engine →
  Style and Lyrics → Plan Score (optional ABC) → Song Tokens → Acoustic
  Synthesis → VAE Decode → Save Song. Every node runs its own real stage.
- **YuE2 Cover / Restyle canvas** — LoadAudio → Analyze Melody (SheetSage2 FP32
  for T4) → Style and Lyrics → Load Engine (loads after analysis) → same chain
  with the extracted score.
- Both canvases are also installed under ComfyUI's **Workflows** menu.
- One engine lock: each wrapper hands over to the other automatically
  (verified stop / `/yue2/release`); GPU preflight before any model work.
- Your asset dataset is used as-is — nothing rebuilt, no model downloads.

## Changed files (9 modified + 4 new)

| File | Change |
|---|---|
| `native_yue2/comfy_pack.py` | **NEW** — the KaggleYuE2 node pack source (11 nodes + web extension + `/yue2/status` + `/yue2/release` routes) |
| `native_yue2/comfy_canvas.py` | **NEW** — programmatic builders for both canvas graphs |
| `native_yue2/comfy_web.py` | **NEW** — frontend extension that opens a canvas from the `?yue2_workflow=` link |
| `tests/test_comfy.py` | **NEW** — 10 CPU checks for pack structure, graph wiring, setup writes |
| `native_yue2/engine.py` | Scoped refactor: pipeline init → `initialize_pipeline()`, Gradio UI → `build_and_launch_ui()` (both still run automatically in the engine process). Sidecar behavior unchanged; the module is now import-safe for ComfyUI |
| `native_yue2/setup.py` | Adds `install_comfyui()`, `write_comfy_pack()`, `request_comfy_release()`; ComfyUI pinned v0.43.2 |
| `native_yue2/tunnel.py` | `ready_path` parameter (Gradio `/config` vs ComfyUI `/system_stats`) — default unchanged |
| `tools/build_fast_notebook.py` | Revision 11 header, release handover in the Gradio cell, new ComfyUI canvas cells |
| `tests/test_native.py` | Exercise the two new startup seams explicitly (5 lines) |
| `README.md` / `AGENTS.md` | Revision 11 documentation + your canvas preference recorded |
| `*.ipynb` (both) | Regenerated from sources (embedded payloads updated) |

## Validation performed (no GPU used)

- **72/72 CPU tests pass** (assets, attention, native, process, tunnel, comfy)
  on PyTorch 2.11.0 CPU — the same torch family Kaggle's T4 image uses (2.11.0+cu128).
- Both canvases were validated against a **real ComfyUI v0.43.2 server**:
  all 11 nodes register with the expected inputs/outputs, the web extension and
  both canvases are served, and ComfyUI's own `/prompt` validator **accepted
  both graphs**.
- Both canvases were opened in a **real browser** and rendered correctly
  (song: 8 nodes, cover: 9 nodes, all links and widgets verified programmatically).
- Engine-sidecar behavior is exercised by the existing native suite through the
  same two startup functions the sidecar calls.

**Not yet verified (needs your Kaggle GPU):** actual T4 generation through the
canvas, CUDA-graph capture inside the ComfyUI process, the T4 attention speedup
(vs the 8.355 tok/s baseline), eight-minute memory peaks, and musical quality.
The logs will print `[YuE2 attention] Confirmed efficient grouped kernel ...`
when the fix engages.

## How to publish (GitHub web UI, one step at a time)

1. Unzip `yue2-music-revision-11.zip`.
2. On github.com open `bothashaun-maker/Music`.
3. For each changed/new file below, open it in GitHub → pencil (Edit) → paste
   the new content → Commit. Or easier: **Add file → Upload files**, and drag
   in these paths from the unzipped folder (GitHub merges them into place):
   - `native_yue2/comfy_pack.py`, `native_yue2/comfy_canvas.py`, `native_yue2/comfy_web.py`
   - `native_yue2/engine.py`, `native_yue2/setup.py`, `native_yue2/tunnel.py`
   - `tests/test_comfy.py`, `tests/test_native.py`
   - `tools/build_fast_notebook.py`
   - `yue2-3b-frontier-full-song-music-generation.ipynb`,
     `yue2-build-kaggle-assets.ipynb`
   - `README.md`, `AGENTS.md`
4. Commit with message: `Revision 11: ComfyUI canvas wrapper (song + cover)`.

## First run on Kaggle

1. Import the updated `yue2-3b-frontier-full-song-music-generation.ipynb`
   (Download raw file → Kaggle import). Attach your existing asset dataset.
2. GPU T4 ×2 + Internet on. Run **Setup**.
3. Run **Open the ComfyUI canvas**. The cell prints the full-song and cover
   Cloudflare links that open the graphs directly.
4. Generate from the canvas (Queue Prompt). Stop interrupts at a step boundary.
   To switch to the Gradio wrapper, stop the canvas cell — the Gradio cell asks
   the canvas server to release the engine automatically.
