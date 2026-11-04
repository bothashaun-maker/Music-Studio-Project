# Delivery — Music revision 15 (canvas engine-lock fix)

**Your error:** `RuntimeError: Cannot verify native engine process ownership` when you
pressed Run on the YuE2 canvas (node 2, YuE2LoadEngine).

**Root cause (found by reading the code, reproduced locally):** the ownership checker
compared the process command line **literally**. The engine route always launches with an
absolute path (`python -u /…/engine.py`), but the ComfyUI canvas server is launched as
`python -u main.py` — a **relative** path from its own folder. The checker demanded the
absolute form, so on the canvas it could never pass. It was not your settings, your
dataset, or anything you did.

**The fix (one function, `native_yue2/process.py::identity`):** the script argument is now
resolved against the process's real working directory (`/proc/<pid>/cwd`) before comparing.
Every security check is kept: same user, exact script, `-u` flag, `YUE2_OUTPUT_ROOT`
environment, not a zombie, PID start time.

**Tested before shipping (4 checks + the full suite):**

1. Canvas route, relative `main.py` — the exact Kaggle scenario → **lock acquired** ✅
2. Managed engine route, absolute path → still works (no regression) ✅
3. Wrong output root in environment → still rejected ✅
4. Missing `-u` flag → still rejected ✅
5. `pytest tests/test_process.py tests/test_comfy.py` → **21 passed** ✅

**Also inside (from revision 14, unchanged):** the self-healing wheelhouse — if a wheel is
missing it prints one clear line and fetches only that wheel from PyPI. Your last log
proved this works: ComfyUI v0.43.2 installed fully (`comfyui-frontend-package 1.57.4`,
`comfy-aimdo 0.6.0`, `comfy-kitchen 0.2.40` all loaded) and the KaggleYuE2 pack registered.

**What to do:**

1. Download the new `FULL-CHAT-AND-ALL-FILES.zip`.
2. Kaggle → delete the old YuE2 notebook → **File → Import Notebook** →
   `yue2-3b-frontier-full-song-music-generation.ipynb`.
3. Internet ON, GPU T4 x2 → **Run All** → open the canvas → press **Run**.

Nothing else changed: no dataset re-upload, same models, same workflows, same outputs.
