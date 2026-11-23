# Music Studio repair — delivered 23 November 2026

For Shaun. Simple summary first, then the numbered details, then what was NOT tested.
Everything below was checked with real runs on this machine before anything was changed.

## 1. What I did, in one line each

1. **Music-Studio.ipynb was dead on Kaggle** — fixed.
2. **Music Studio Dataset could never start a studio** (missing whisper binary) — fixed.
3. **YuE2_ComfyUI_Kaggle.ipynb (standard ComfyUI canvas) was stale** — rebuilt on the proven revision-15 sources.
4. **Big cover-song WAV uploads could lose bytes silently** — both resumable uploaders now verify every piece with SHA-256.
5. **The repo's own test suite was red** — fixed; every suite that can run here is green.
6. **Kaggle SDK, all 30 pinned downloads, and all 4 pinned source commits** — verified against the real thing.

## 2. The problems, reproduced first (as agreed: no fix without reproduction)

1. **Music-Studio.ipynb** carried payload keys like `music_studio\launch.py` (built on Windows).
   On Kaggle's Linux this writes twelve flat files whose names contain a backslash — not a package.
   I ran the notebook's own extraction loop on Linux: `python -m music_studio.launch` died with
   `ModuleNotFoundError: No module named 'music_studio'`. Reproduced before fixing.
2. **The Dataset notebook compiles a runtime the studio can never launch.** `launch.py` requires
   `whisper/whisper-cli` (karaoke timing) and the studio looks only in `<karaoke>/runtime/whisper/`;
   its own fallback download is an ARM build, useless on Kaggle x86_64. The builder had **no whisper
   stage** (it was lost in an earlier edit — the docs still claimed it existed). So after ~1 hour of
   compiling and 25 GB of downloads, the first launch would crash on the missing binary.
3. **The standard ComfyUI canvas notebook still embedded the pre-revision-15 runtime**: old ComfyUI
   pin `bc5f880…` (v0.42 era), plain pip with no saved-wheelhouse fallback, un-repaired engine sources,
   and **no resumable cover upload at all**.
4. **Big WAV uploads, checked end to end** (real aiohttp servers, a 104 MB WAV, on CPU):
   - ComfyUI's standard Load Audio upload is one request, and ComfyUI passes `--max-upload-size`
     (default **100 MB**, verified in ComfyUI's source at the pinned commit) → **HTTP 413**. A big
     cover cannot go through it at all.
   - The revision-15 cover uploader and the Timestamp Studio uploader were resumable but checked
     **size only**. I flipped one byte inside the first piece and sent it: both servers **accepted it
     (HTTP 200)** and assembled "ok" — the saved song was the damaged bytes, no error anywhere.
   - Music Studio's own Rust uploader already verified per-piece and whole-file SHA-256; I did not change it.
5. **Two tests in `tests/music_studio/test_dataset_flow.py` were internally broken** (a mock returned an
   archive the builder had already deleted; a setup forgot to mark compilers executable), so the
   documented test command failed on every machine.

## 3. What I changed (all files inside the repo)

1. `tools/build_music_studio_notebooks.py` — payload keys are now POSIX (`music_studio/…`) and the
   notebook's extraction loop normalises `\` to `/` before writing, so a payload built on any machine
   unpacks correctly on Linux.
2. `music_studio/build_runtime.py` — restored the **whisper.cpp build stage** (pinned commit `d1be6fde`
   = tag b5454, CPU-only, shared libs, tests/server off). The saved runtime now contains
   `whisper/whisper-cli` with its own `libwhisper`/`libggml` libraries beside it, and `assemble()`
   refuses to finish without it. Because this file is pinned by checksum, `sources.json` was
   regenerated — the Dataset gets a **new handle suffix** (`music-studio-dataset-v1-<new suffix>`).
   An old Dataset, if one exists, cannot be reused by the new notebook (by design — it could never start).
3. `revision15/native_yue2/cover_upload.py` + `cover_upload_web.py` — every 1 MB piece now carries a
   SHA-256 from the browser; the server verifies before saving and refuses a damaged piece (HTTP 400,
   nothing stored); finished pieces are still kept for resume; `finish` streams the whole file and
   records its SHA-256 in the receipt and returns it (browser prints it in the console).
4. `revision15/timestamp_studio/comfy_pack.py` — same treatment for the Timestamp Studio uploader
   (8 MB pieces + `sha` + server verification + whole-file SHA-256 in `complete.json`).
5. `tools/build_comfy_notebook.py` — rewritten: `YuE2_ComfyUI_Kaggle.ipynb` is now generated from
   `revision15/kaggle_yue2/` + `revision15/native_yue2/` (the exact proven sources), canvas-only
   startup, POSIX-safe keys, and it refreshes `workflows/yue2_song.json` / `yue2_cover.json` from the
   revision-15 graph builder so the repo copies match what the notebook installs.
6. `tests/music_studio/test_dataset_flow.py` — the two broken tests fixed; revision-15 upload tests
   updated for the checksum protocol plus new corruption tests.
7. `COMFY_CANVAS.md` and `docs/music-studio/VALIDATION.md` — updated to match reality (new pin, wheelhouse
   fallback, checksum-verified upload, whisper stage restored, and this session's evidence).

## 4. Proof (what I actually ran)

1. Backslash reproduction → `ModuleNotFoundError` before the fix; after the rebuild the embedded
   package imports from the support directory. Same smoke-import check done for all rebuilt notebooks.
2. Whisper proof build: pinned whisper.cpp compiled on CPU with the pinned cmake 3.31.6 / ninja;
   `ldd` resolves its libraries beside the binary; `whisper-cli --help` runs.
3. Kaggle SDK: the full Dataset `publish()` flow ran against the **real `kaggle==2.0.2` wheel from PyPI**
   with only the network transport stubbed — authentication, the SDK's own create/upload methods,
   1 status probe + 5 symlinked single-file blob uploads + 1 private create request, receipts written.
   Also: `kaggle==2.0.2` needs `six` at import; pip installs it transitively via python-dateutil, so
   the notebook's `pip install --target` step is safe.
4. All **30** pinned model/toolchain URLs answered with exactly their pinned byte sizes; all 4 pinned
   upstream commits (yue2-studio, yue.cpp, HOT-Step, whisper.cpp) fetched by commit hash.
5. Upload verification (logs attached): OLD uploader accepted the damaged piece and assembled it
   silently; FIXED uploader refused it with HTTP 400 and a clean upload assembled **byte-identically**,
   with the file's SHA-256 recorded — for BOTH canvases. Standard Load Audio 104 MB → HTTP 413.
6. Test suites, all green: `tests/music_studio` (25), revision-15 cover-upload tests (9, including the
   shipped browser script run in Node with real crypto), `test_notebook_startup`, `test_assets`,
   `test_process`, `test_tunnel`.

## 5. How to use it (Kaggle)

1. Download `Music-fixed-2026-11-23.zip` (or the individual notebooks) and import the notebook you need:
   - **Song / cover**: `YuE2_Music_Revision15.ipynb` or `YuE2_ComfyUI_Kaggle.ipynb` (GPU T4 ×2, Internet ON).
   - **Big WAV cover**: press **Upload song (resumable)** on the LoadAudio node — up to 2 GiB, checksum-verified.
   - **Timestamps**: `Song-Timestamp-Studio-Canvas.ipynb` — the studio's 📤 uploader is now checksum-verified too.
   - **Dataset**: run `Music-Studio-Dataset.ipynb` once (Accelerator None, Internet ON) — it now produces a
     runtime that includes `whisper-cli`, so `Music-Studio.ipynb` can actually start afterwards.
2. The Dataset gets a **new handle** (fingerprint changed). Attach that new Dataset to Music-Studio.ipynb.
3. Nothing runs automatically; press Create/Queue Prompt yourself, as before.

## 6. NOT tested — read this before trusting it

1. **Nothing here has run on Kaggle.** No Kaggle credentials or GPU exist in this sandbox. The Dataset
   build (CUDA compile + 25 GB upload), a real GPU generation, and the live Cloudflare links remain
   unverified — same limits as the previous validation.
2. **Torch-dependent suites were not run** (no torch in this sandbox): root `test_attention`,
   `test_comfy_canvas`, `test_native`, and the revision-15 studio/runtime suites
   (`test_revision15_uploads.py` and friends — the upload tests there were updated but not executed).
3. **The whisper stage was proven by compiling the pinned sources on CPU here**, not inside the full
   Dataset build on Kaggle; the engine CUDA compile was not run at all in this sandbox.
4. **The shipped browser JS is verified by the Node end-to-end test (crypto.subtle works there), but a
   real browser upload through Cloudflare was not tested.** `crypto.subtle` requires a secure context:
   localhost and the trycloudflare HTTPS link both qualify, but that was not exercised live.
5. **ComfyUI's 100 MB default cap was verified from ComfyUI's source at the pinned commits**, not by
   running a full ComfyUI server; the 413 behaviour was reproduced with the same aiohttp limit ComfyUI passes.
6. Kaggle's current GPU image driver version (the launcher needs 580+) was not verifiable from here.
7. The Model Pack Builder notebook (`music_studio/Music_Studio_Model_Pack_Builder.ipynb`) was **left
   unchanged**: it versions the existing `music-studio-model-pack` Dataset with `kagglehub` and pins no
   hashes, despite its README claiming SHA256 checks. Changing it was out of scope for this pass; the
   README overstatement is real and should be fixed separately if you want that notebook hardened.

## 7. Files in this delivery

- `Music-fixed-2026-11-23.zip` — the whole fixed repo worktree (165 files; integrity tested).
- `Music-Studio.ipynb`, `Music-Studio-Dataset.ipynb`, `YuE2_ComfyUI_Kaggle.ipynb`,
  `YuE2_Music_Revision15.ipynb`, `Song-Timestamp-Studio-Canvas.ipynb`, `yue2-music-revision-15.zip` — the rebuilt deliverables, copied out for convenience.
- `upload-verification-OLD.log` / `upload-verification-FIXED.log` — the big-WAV evidence runs.
- The worktree at `gh/Music-fix` holds the same changes, uncommitted, for review with `git diff`.
