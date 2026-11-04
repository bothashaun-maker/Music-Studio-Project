# Delivery — Music revision 14 (the crash fix)

**What was broken:** your Kaggle log died at the ComfyUI install step with
`Could not find a version that satisfies the requirement comfyui-frontend-package==1.57.4 (from versions: none)`.
Your saved asset wheelhouse never contained the ComfyUI-only packages, and the notebook
you were running had no fallback — so it crashed instead of fetching them.

**What changed in revision 14 (3 things, nothing else):**

1. **Self-healing installs.** `kaggle_yue2/runtime.py` now tries your saved wheelhouse
   first; if a wheel is missing it prints one clear line and fetches ONLY the missing
   wheels from PyPI (your saved wheels still win, your version pins still apply).
   If both routes fail you get a plain-English error, never a raw traceback.
   This exact path was tested live: your error message reproduced → fallback → success.
2. **One ComfyUI pin everywhere.** `kaggle_yue2/runtime.py` said commit `bc5f880…` while
   the real installer pins `423cbd2…` (v0.43.2). Both now say `423cbd2…`. The old
   constant was dead code, but a mismatch waiting to happen is still a landmine.
3. **Rebuilt notebooks.** `yue2-3b-frontier-full-song-music-generation.ipynb` and
   `yue2-build-kaggle-assets.ipynb` rebuilt from the fixed sources (all 14 embedded
   files compile; payload round-trip verified).

**What did NOT change:** your dataset, your models, your workflows, the canvas, the
Gradio opt-in, Timestamp Studio. You do NOT need to re-upload the asset dataset.

**Verified today:** PyPI has every pinned ComfyUI v0.43.2 package for Kaggle's
Python 3.13 (`comfyui-frontend-package==1.57.4`, `comfyui-workflow-templates==0.11.100`,
`comfyui-embedded-docs==0.5.15`, `comfy-aimdo==0.6.0`, `comfy-kitchen==0.2.40`,
`transformers==4.57.6` — all universal `py3-none-any` wheels or abi3).
Internet must stay ON (it already was — the ComfyUI checkout needs GitHub).

**Timestamp Studio (separate fix, same zip):** the canvas notebook in the archive was
an old build with no upload page. The rebuilt one prints the
`📤 Upload songs` link in the ready banner and serves the chunked uploader; tested
end-to-end on real ComfyUI v0.43.2 (uploader page, 6 nodes, full run, ±0.46 s).
