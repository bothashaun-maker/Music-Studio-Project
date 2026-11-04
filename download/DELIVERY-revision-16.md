# Delivery — Music revision 16 (no more repeated downloads + canvas node hand-off fix)

**What you saw tonight, in simple words:**

1. Your models did **NOT** download again. Your log shows it: `Using saved Kaggle assets:
   /kaggle/input/datasets/janpierrrewiet/yue2-music-assets` — every model came from your
   dataset. Your 12 GB stayed safe on Kaggle.
2. What DID download every session was the **ComfyUI app itself** (~600 MB of wheels +
   a source fetch from GitHub), because Kaggle wipes all temporary files when a session
   ends, and your dataset was built **before** those app files existed. That is why you
   saw downloads "again" every single time. That was my gap, not your mistake.
3. After that, the engine **loaded fine** (my earlier fix worked — see
   `YuE2 engine loaded in 55.4s` in your log), but the next node crashed because the
   Load Engine node handed a `True` flag to the next node instead of the engine itself
   (`AttributeError: 'bool' object has no attribute '_cancelled'`). Fixed.

**What changed in revision 16:**

1. **The builder now saves the whole ComfyUI app inside your dataset** — the pinned
   source copy (`comfyui-snapshot.tar.gz`) plus every wheel ComfyUI needs. It also
   reuses your existing dataset: attach your current yue2-assets as input to the
   builder, and it **copies your saved model files instead of downloading any model**.
   Only the small app wheels get fetched, once.
2. **Generator sessions with the rebuilt dataset run fully offline** — no models, no
   GitHub fetch, no package downloads. Only the Cloudflare link uses the network.
   With your OLD dataset attached, everything still works; it just fetches the small
   app set from PyPI (with one clear line explaining it).
3. **The canvas node chain now passes the engine itself** between nodes, and the whole
   chain (Run Context → Load Engine → Style/Lyrics → Plan Score → Song Tokens →
   Acoustic Synthesis → VAE Decode → Save Song) is now **executed in tests**, not just
   read. That is how this crash class gets caught before it reaches you.
4. Extra hardening: the engine lock works with any launch style, a stale `plan.json`
   checksum conflict was removed, and pip prints exactly what is happening and why.

**Tested before shipping:** 91 tests passed, including the full canvas chain on CPU,
the offline snapshot restore of the real pinned ComfyUI checkout, the
download-only-the-gap wheel logic, and a fully offline resolution check.

**What to do (in the morning, three steps):**

1. Download `FULL-CHAT-AND-ALL-FILES.zip` (or `yue2-music-revision-16.zip`).
2. Kaggle → import the new `yue2-build-kaggle-assets.ipynb` → **Add Input → your
   existing yue2-assets dataset** → Internet ON, no GPU → **Save Version → Save & Run
   All** → wait for `COMPLETE` (your models are copied, not downloaded; this run is
   short). Then attach the new saved output in your music notebook instead of the old
   dataset.
3. Kaggle → delete the old YuE2 notebook → **File → Import Notebook** →
   `yue2-3b-frontier-full-song-music-generation.ipynb` → Internet ON, GPU T4 ×2 →
   attach the **new** dataset → Run All → open the canvas → press **Run**.

Nothing else changed: same engine, same workflows, same outputs, same songs.
