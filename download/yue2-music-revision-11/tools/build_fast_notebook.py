"""Build the standalone notebook around the original native FP16 Kaggle engine."""
from pathlib import Path
import base64
import json
import textwrap
import zlib

ROOT = Path(__file__).resolve().parents[1]


def cell(kind, source):
    source = textwrap.dedent(source).strip() + '\n'
    result = {'cell_type': kind, 'metadata': {}, 'source': source.splitlines(keepends=True)}
    if kind == 'code':
        result.update(execution_count=None, outputs=[])
    return result


def build():
    files = {}
    for directory in ('kaggle_yue2', 'native_yue2'):
        for p in sorted((ROOT / directory).glob('*.py')):
            files[str(p.relative_to(ROOT))] = p.read_text()
    payload = base64.b64encode(zlib.compress(json.dumps(files).encode(), 9)).decode()
    bootstrap = '''
    import base64, json, os, sys, zlib
    from pathlib import Path
    if "app" in globals():
        app.stop()  # Release a managed server from the earlier ComfyUI notebook.
    if "native_process" in globals() and native_process.poll() is None:
        native_process.terminate()
        try:
            native_process.wait(timeout=20)
        except Exception:
            native_process.kill()
            native_process.wait(timeout=10)
    # Close only the original YuE2 pipeline if a previous notebook left it
    # inside this kernel. Other model variables/processes are not cleared.
    legacy_pipe = globals().get("pipe")
    if (legacy_pipe is not None and legacy_pipe.__class__.__module__ == "yue2.pipeline"
            and legacy_pipe.__class__.__name__ == "YuE2Pipeline"):
        if isinstance(globals().get("CANCEL"), dict):
            CANCEL["stop"] = True
        legacy_demo = globals().get("demo")
        if legacy_demo is not None and legacy_demo.__class__.__module__.startswith("gradio."):
            legacy_demo.close()
        legacy_pipe.close()
        globals().pop("pipe", None)
        import gc
        gc.collect()
        torch_module = sys.modules.get("torch")
        if torch_module is not None and torch_module.cuda.is_initialized():
            torch_module.cuda.empty_cache()
        print("Closed the previous in-kernel YuE2 pipeline; saved song files remain.")
    support = Path("/kaggle/temp/yue2_native_support")
    support.mkdir(parents=True, exist_ok=True)
    payload = "PAYLOAD"
    for relative, contents in json.loads(zlib.decompress(base64.b64decode(payload))).items():
        path = support / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    for name in list(sys.modules):
        if name.split(".")[0] in {"native_yue2", "kaggle_yue2"}:
            del sys.modules[name]
    if str(support) not in sys.path:
        sys.path.insert(0, str(support))
    from native_yue2.setup import install
    ROOT = "/kaggle/temp/yue2_native"
    OUTPUTS = "/kaggle/working/yue2_native/runs"
    ASSET_DATASET = "auto"  # Attach saved YuE2 assets with Add Input. No download fallback.
    native_python, native_env = install(ROOT, OUTPUTS, assets=ASSET_DATASET)
    print("Setup completed. Run one of the two UI cells: the Gradio generator or the ComfyUI canvas.")
    '''.replace('PAYLOAD', payload)
    cells = [cell('markdown', '''
        # YuE2 on Kaggle — native FP16 engine (revision 11, two wrappers)

        **First time:** run `yue2-build-kaggle-assets.ipynb` once on Kaggle with
        Internet and **no GPU**, then save its outputs as a private dataset.
        Add that dataset to this notebook with **Add Input**. You can also attach
        the saved builder notebook's output directly. Nothing large needs to be
        downloaded to your PC or uploaded from your PC.

        **Every music session:** attach that saved input, select **GPU T4 ×2**
        and enable Internet. Setup reads weights from
        `/kaggle/input` and installs dependencies from saved local wheels.
        Missing/incompatible assets cause an early error, never a replacement
        download. Keep the same Kaggle Python/image version as the builder;
        upgrades can require rebuilding the dependency bundle.

        This restores the original
        `yue2_infer 0.1.5` engine: FP16 transformer on GPU 0, CUDA-graph AR decoding
        with SDPA, and tiled FP32 VAE on GPU 1. Default generation uses **Direct to
        audio**, **16 Euler steps**, CFG **1.0**, and an **8-minute safety ceiling**.
        The model chooses a natural ending from your prompt and lyrics. It does
        not have to fill the ceiling. A token-limit cutoff is reported separately.

        **Two wrappers, one engine.** Run **one** of the two UI cells after setup:

        * **Open the generator** — the original Gradio interface (Gradio share
          link + optional Cloudflare link), unchanged from revision 10.
        * **Open the ComfyUI canvas (new)** — a pinned ComfyUI with the
          **KaggleYuE2** node pack. The Cloudflare link opens a real node graph —
          Run Context → Load Engine → Style/Lyrics → Plan Score → Song Tokens →
          Acoustic Synthesis → VAE Decode → Save Song — using this same engine,
          the same FP16 precision, attention layout and saved-run format. A
          second canvas covers/restyles an uploaded song via SheetSage2 melody
          extraction. Each node runs its own stage; nothing is one wrapper node.

        Both wrappers share one engine lock: starting one releases the other, and
        a GPU-memory preflight runs before any model work. ComfyUI runs from a
        session-only pinned checkout (v0.43.2) under the same constraints; your
        asset dataset is not rebuilt and no model is downloaded again.

        **No diagnostic song runs automatically.** Cover your own song in either
        wrapper by uploading its WAV/FLAC/MP3, pasting your original lyrics, and
        analyzing the melody first. Extracted-score regeneration can change
        timing, voice and arrangement; it is not exact audio-to-audio copying.
        Optional **Transcribe lyrics too** uses Whisper when needed.

        **T4 attention change:** equivalent grouped-head views make PyTorch's
        memory-efficient kernel eligible, instead of the native T4 GQA math path.
        The first supported CUDA dispatch is verified and logged. Unsupported
        shapes retain native attention and are reported. CPU equivalence checks
        passed; actual T4 speed improvement has not been measured.

        Durations are maximums. A natural early ending or token cutoff is reported.
        Long acoustic generations may span multiple chunks; listen at the reported
        boundaries. Seven/eight-minute performance and continuity remain unverified.

        The small installed environment uses session-only `/kaggle/temp/yue2_native`.
        Large models stay in the attached read-only Kaggle input dataset.
        Song audio, exact tokens and recovery latents use
        `/kaggle/working/yue2_native/runs`. The paths may share underlying storage;
        setup prints actual free space rather than assuming a separate 50 GB quota.
        Old notebook caches and files are preserved.

        **Process protection:** setup and launch stop only verified older engines
        using this script/output root, including survivors of a kernel restart.
        A process lock prevents two managed engines from loading together. GPU
        memory is checked before loading and before generation. An unrecognized
        GPU process is reported and left running; setup stops before generation.
        CUDA OOM saves GPU process details and releases the failed engine's model.

        **After generation, download the complete run ZIP in the wrapper you used,
        or Save Version with outputs in Kaggle before ending the session.** A saved
        draft or a notebook download containing logs does not preserve audio files.
        '''), cell('code', bootstrap), cell('markdown', '''
        **Open the generator (Gradio wrapper).** This cell loads the saved
        full-precision model assets and prints the existing **Gradio link** plus an
        additional **Cloudflare link**, as the original notebook did. Both reach the
        same interface, uploaded files and engine. Your existing asset dataset works;
        no rebuild is needed. The optional Cloudflare executable is downloaded
        to Kaggle once per session if it is not already cached. Models and Python
        packages still load from your dataset, with network downloads disabled.
        If a ComfyUI canvas server holds the engine, this cell asks it to release
        the weights first; both wrappers never hold the model at the same time.

        Use the Cloudflare link as an alternative route for your unchanged WAV.
        Quick Tunnels do not guarantee availability or SSE live-progress support;
        a Cloudflare link is not proof the 75 MB upload issue is fixed. The
        original Gradio link remains available. Neither route starts generation.
        If Cloudflare fails, its error is printed and the Gradio app keeps running.
        A temporary link grants access to the UI; keep it private.
        The cell stays running while the UI is available. Reuse it for additional
        songs so the transformer can stay loaded. A stopped cell ends this process.

        The UI defaults to **Up to 8 min**. This allows seven/eight-minute songs
        while preserving natural shorter endings. Supply complete lyrics with
        sections, instrumental passages and an outro. A lower selected ceiling
        can cut a song off; it does not tell the model to finish there.
        The original generation defaults are restored; no speed is promised for
        long songs. The status panel reports actual AR execution and stage times.
        '''), cell('code', r'''
        import subprocess, re
        from native_yue2.tunnel import CloudflareAccess
        if "cloudflare_access" in globals():
            cloudflare_access.close()
        ENABLE_CLOUDFLARE = True  # Additional link; the existing Gradio link stays available.
        cloudflare_access = CloudflareAccess(
            ROOT, assets=native_env.get("YUE2_ASSET_DATASET"),
            log=Path(OUTPUTS).parent / "runtime/cloudflared.log")
        cloudflare_attempted = False
        engine = support / "native_yue2/engine.py"
        log_path = Path(OUTPUTS).parent / "runtime/engine.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        from native_yue2.process import start_engine
        from native_yue2.setup import request_comfy_release
        request_comfy_release()  # A running ComfyUI canvas releases the engine; the lock hands over.
        native_process = start_engine(native_python, engine, native_env, ROOT, OUTPUTS)
        try:
            with log_path.open("a") as log:
                for line in native_process.stdout:
                    log.write(line)
                    log.flush()
                    print(line, end="", flush=True)
                    local = re.search(r"Running on local URL:\s+http://127\.0\.0\.1:(\d+)", line)
                    if ENABLE_CLOUDFLARE and local and not cloudflare_attempted:
                        cloudflare_attempted = True
                        try:
                            link = cloudflare_access.start(int(local.group(1)), env=native_env)
                            print(f"\nAdditional Cloudflare link: {link}", flush=True)
                            print("The Gradio share link remains available. Both use the same engine.", flush=True)
                            print("Temporary Cloudflare links may not stream live Gradio progress reliably. "
                                  "Keep both links available; neither starts a song automatically.", flush=True)
                        except Exception as exc:
                            print(f"Cloudflare is unavailable: {exc}\nThe Gradio link is still available.", flush=True)
            if native_process.wait() != 0:
                raise RuntimeError(f"Native engine stopped. Inspect {log_path}")
        finally:
            cloudflare_access.close()
            if native_process.poll() is None:
                native_process.terminate()
                try:
                    native_process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    native_process.kill()
                    native_process.wait(timeout=10)
        '''), cell('markdown', '''
        **Open the ComfyUI canvas (new in revision 11).** This cell installs a
        pinned, session-only ComfyUI **v0.43.2** with the **KaggleYuE2** node
        pack and starts a persistent server. The printed **Cloudflare link opens
        the full node graph directly**; the plain link opens ComfyUI normally.
        Both canvases also appear under ComfyUI's **Workflows** menu:

        * **YuE2 Full Song** — Run Context → Load Engine → Style/Lyrics →
          Plan Score (optional) → Song Tokens → Acoustic Synthesis → VAE Decode
          → Save Song. Direct-to-audio by default; switch the Plan Score node to
          Melody or Full mode for an ABC score, or paste a score into a
          **YuE2 Custom ABC** node.
        * **YuE2 Cover / Restyle** — upload your song with the standard
          **LoadAudio** node, analyze the melody (SheetSage2, FP32 for T4), then
          write the new style. The engine loads only after analysis finishes.

        Every node executes its real stage against the **same FP16 engine** as
        the Gradio wrapper: same precision, attention layout, token ceilings,
        solver defaults and saved-run files (`status.json`, tokens, latents,
        masters, ZIP) under `/kaggle/working/yue2_native/runs`. One **seed** on
        the Run Context node drives the whole song. The **Stop** button in
        ComfyUI interrupts at a step boundary and saves earlier stages. The
        **YuE2 Release Engine** node (or stopping this cell) frees the model so
        the Gradio wrapper can run; each wrapper takes the lock from the other
        automatically.

        ComfyUI's extra dependencies install from the network under the same
        Kaggle constraints (torch/transformers stay pinned); this does not
        rebuild your asset dataset and downloads no model weights. Keep this
        cell running while using the canvas. Quick Tunnels do not guarantee
        availability; if the link fails, the cell's log shows the local server
        state and the Gradio wrapper remains available.
        '''), cell('code', r'''
        import json, re, socket, subprocess, threading, time
        import urllib.request
        from IPython.display import HTML, display
        from native_yue2.setup import install_comfyui, COMFY_PORT
        from native_yue2.tunnel import CloudflareAccess

        ENABLE_CLOUDFLARE = True  # Additional links; the local server is unaffected.

        def comfy_ready(port=COMFY_PORT):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/system_stats", timeout=3) as response:
                    return response.status == 200
            except Exception:
                return False

        if "comfy_tunnel" in globals() and comfy_tunnel is not None:
            comfy_tunnel.close()
        if "comfy_process" in globals() and comfy_process.poll() is None:
            comfy_process.terminate()
            try:
                comfy_process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                comfy_process.kill()
                comfy_process.wait(timeout=10)

        if comfy_ready():
            print("ComfyUI server already running; reusing it.", flush=True)
        else:
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", COMFY_PORT)) == 0:
                    raise RuntimeError(f"Port {COMFY_PORT} is occupied by another program.")
            comfy_dir, comfy_env = install_comfyui(ROOT, OUTPUTS, native_env)
            log_path = Path(OUTPUTS).parent / "runtime/comfyui.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            comfy_log = log_path.open("a")
            comfy_process = subprocess.Popen(
                [native_python, "-u", "main.py", "--listen", "127.0.0.1", "--port", str(COMFY_PORT),
                 "--output-directory", str(OUTPUTS), "--disable-auto-launch", "--preview-method", "none"],
                cwd=str(comfy_dir), env=comfy_env, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1)

            def _drain(stream, log):
                for line in stream:
                    log.write(line)
                    log.flush()
                    print(line, end="", flush=True)
                log.close()

            threading.Thread(target=_drain, args=(comfy_process.stdout, comfy_log), daemon=True).start()
            for _ in range(150):
                if comfy_process.poll() is not None:
                    raise RuntimeError("ComfyUI exited during startup; inspect the log above.")
                if comfy_ready():
                    break
                time.sleep(2)
            else:
                raise TimeoutError("ComfyUI did not become ready; inspect the log above.")

        object_info = json.loads(urllib.request.urlopen(
            f"http://127.0.0.1:{COMFY_PORT}/object_info", timeout=15).read().decode())
        missing = [name for name in ("YuE2RunContext", "YuE2LoadEngine", "YuE2SaveSong") if name not in object_info]
        if missing:
            raise RuntimeError(f"KaggleYuE2 nodes missing from the server: {missing}; inspect the startup log.")

        comfy_tunnel = CloudflareAccess(
            ROOT, assets=native_env.get("YUE2_ASSET_DATASET"),
            log=Path(OUTPUTS).parent / "runtime/comfy-cloudflared.log")
        base_link = None
        if ENABLE_CLOUDFLARE:
            try:
                base_link = comfy_tunnel.start(COMFY_PORT, ready_path="/system_stats")
            except Exception as exc:
                print(f"Cloudflare is unavailable: {exc}\nThe local server keeps running; the Gradio wrapper stays available.", flush=True)
        print("\nIn ComfyUI: Workflows → YuE2 Full Song / YuE2 Cover · or press Run on the opened canvas", flush=True)
        if base_link:
            song_link = base_link + "/?yue2_workflow=song"
            cover_link = base_link + "/?yue2_workflow=cover"
            print("Full-song canvas: ", song_link, flush=True)
            print("Cover canvas:     ", cover_link, flush=True)
            display(HTML('<a href="' + song_link + '" target="_blank" rel="noopener noreferrer">Open the YuE2 full-song canvas</a><br>'
                         '<a href="' + cover_link + '" target="_blank" rel="noopener noreferrer">Open the YuE2 cover canvas</a><br>'
                         '<a href="' + base_link + '" target="_blank" rel="noopener noreferrer">Open plain ComfyUI</a>'))
        print("Keep this Kaggle session and this cell running while using ComfyUI.", flush=True)
        print("Generate from the canvas: Queue Prompt. Stop interrupts at a step boundary and saves earlier stages.", flush=True)

        try:
            while comfy_process.poll() is None:
                time.sleep(5)
            raise RuntimeError("ComfyUI server stopped; inspect the log above.")
        finally:
            comfy_tunnel.close()
        '''), cell('markdown', '''
        **Find and preserve your song.** Each attempt has its own folder under
        `/kaggle/working/yue2_native/runs`, whatever wrapper produced it. After a
        successful generation the wrapper offers WAV, FLAC, and a complete ZIP
        containing settings, tokens, timings and recovery latents. Download it
        before stopping. The folder also appears under Kaggle Output at
        `yue2_native/runs`.
        `status.json` records the measured audio length and any cutoff; it does not
        establish musical completeness. Listen to the ending and chunk boundaries.

        Run the next cell after stopping the wrapper to list all saved attempts. It
        starts no model or generation. Files still need to be downloaded or saved
        with a Kaggle output version before the session is discarded.
        '''), cell('code', '''
        from IPython.display import FileLink, display
        for directory in sorted(Path(OUTPUTS).glob("*")):
            if directory.is_dir():
                status = directory / "status.json"
                print(directory.name, status.read_text() if status.exists() else "Partial run")
                for filename in ("audio.wav", "audio.flac"):
                    if (directory / filename).exists():
                        display(FileLink(str(directory / filename)))
        for archive in sorted(Path(OUTPUTS).glob("*.zip")):
            display(FileLink(str(archive)))
        '''), cell('markdown', '''
        **Optional decode recovery.** If audio decoding/export failed after
        `latent.npy` and its manifest were saved, stop the UI first and point the
        next cell at that run folder. This checks the latent checksum and original
        model weights, and decodes to a new folder without regenerating music
        tokens or the acoustic latents. For a new session, attach the saved run ZIP
        as a Kaggle input and extract it first. Setup and the original model files
        from the attached dataset are still required. ComfyUI artifacts from revision 2 use a different format.
        '''), cell('code', '''
        RECOVER_RUN = None  # Folder containing latent.npy and latent_manifest.json
        if RECOVER_RUN:
            if "native_process" in globals() and native_process.poll() is None:
                raise RuntimeError("Stop the UI cell before decoding a saved run")
            recovery_env = dict(native_env, YUE2_RECOVER_RUN=str(Path(RECOVER_RUN).resolve()))
            subprocess.run([native_python, "-u", str(support / "native_yue2/engine.py")],
                           env=recovery_env, check=True)
        '''), cell('markdown', '''
        Based on the original AIQUEST Academy notebook in Movies commit
        `fcf4d45dc5dbca57b39e54311807410cdf41f737`.
        Sources: [YuE2-3B](https://huggingface.co/m-a-p/YuE2-3B),
        [YuE2 VAE](https://huggingface.co/m-a-p/YuE2-Vae).
        The native inference wheel and model revisions are pinned; wheel and
        model checksums are verified. Upstream model/license terms apply.
        Source and checks are included in the Music repository for review.
        '''),
    ]
    return {'cells': cells, 'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'},
        'kaggle': {'accelerator': 'nvidiaTeslaT4', 'isGpuEnabled': True, 'isInternetEnabled': True},
    }, 'nbformat': 4, 'nbformat_minor': 4}


def build_asset_notebook():
    files = {}
    for directory in ('kaggle_yue2', 'native_yue2'):
        for p in sorted((ROOT / directory).glob('*.py')):
            files[str(p.relative_to(ROOT))] = p.read_text()
    payload = base64.b64encode(zlib.compress(json.dumps(files).encode(), 9)).decode()
    bootstrap = """
    import base64, json, os, sys, zlib, subprocess
    from pathlib import Path
    support = Path("/kaggle/temp/yue2_asset_builder_support")
    support.mkdir(parents=True, exist_ok=True)
    payload = "PAYLOAD"
    for relative, contents in json.loads(zlib.decompress(base64.b64decode(payload))).items():
        path = support / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    for name in list(sys.modules):
        if name.split(".")[0] in {"native_yue2", "kaggle_yue2"}:
            del sys.modules[name]
    if str(support) not in sys.path:
        sys.path.insert(0, str(support))
    from native_yue2.setup import install
    BUILDER_ROOT = "/kaggle/temp/yue2_asset_builder"
    ASSET_OUTPUT = "/kaggle/working/yue2-assets"
    native_python, native_env = install(
        BUILDER_ROOT, "/kaggle/temp/yue2_asset_builder_records/runs",
        assets=None, require_gpu=False)
    subprocess.run([native_python, "-u", "-m", "native_yue2.assets",
                    "--build", ASSET_OUTPUT, "--runtime-root", BUILDER_ROOT],
                   env=native_env, check=True)
    """.replace('PAYLOAD', payload)
    cells = [cell('markdown', """
        # YuE2 — save Kaggle assets once (revision 9)

        **Internet ON; accelerator None.** No GPU model or song is run.
        Downloads go directly to Kaggle, not through your home connection.
        This saves the pinned YuE2/VAE, SheetSage2/MERT, optional Whisper,
        Python overlay wheels, bootstrap pip and Gradio tunnel executable.
        Weights are saved once without a duplicate Hub blobs tree.

        Keep this notebook **private**. Use **Save Version → Save & Run All**
        with outputs to build and preserve `/kaggle/working/yue2-assets` in one
        saved run. Wait for **COMPLETE** in its logs. No test song follows.
        You do not need to run it interactively first and repeat the download.
        In your music notebook choose **Add Input → Notebook Output Files**
        and select the completed saved builder version. That is already reusable
        Kaggle storage; you do not need to download/re-upload any files.

        If you specifically want a named **Dataset**, use the optional publish
        cell below from this Kaggle session. It uploads directly from Kaggle to
        your account and creates a **private** dataset. The normal generator
        accepts either the dataset or saved notebook output automatically.

        Keep the same Python minor version and preinstalled scientific package
        versions in builder and generator. If Kaggle changes the image, the
        generator explains the mismatch before any model work. Rebuilding on
        the new image may be necessary. This is not a portable copy of all CUDA.
        Enough output storage for all models is required; an interrupted build
        has no complete assets.json and cannot be mistaken for a finished bundle.
        Model licenses/cards are retained; upstream terms still apply.
        """), cell('code', bootstrap), cell('markdown', """
        **Optional: create a named private dataset, directly from Kaggle.**
        Set DATASET_HANDLE to `your-kaggle-username/yue2-music-assets` and run
        the next cell. Leave it as None if using saved notebook outputs instead.
        KaggleHub needs your Kaggle account authentication. If it requests a
        token, configure Kaggle authentication privately; never paste credentials
        into this notebook. New datasets are private by default in this API;
        choose a new unused slug to avoid updating an older public dataset.
        After upload, attach it using **Add Input → Your Datasets**. Keep the
        dataset private. No model files travel through your home computer.
        """), cell('code', """
        DATASET_HANDLE = None  # Example: "janpierrrewiet/yue2-music-assets"
        if DATASET_HANDLE:
            from native_yue2.assets import validate_assets
            validate_assets(ASSET_OUTPUT, full=True)
            import kagglehub
            if not hasattr(kagglehub, "dataset_upload"):
                raise RuntimeError("This Kaggle image needs a newer KaggleHub for dataset_upload. "
                                   "Use saved notebook outputs now, or update KaggleHub in this builder only.")
            kagglehub.dataset_upload(
                DATASET_HANDLE, ASSET_OUTPUT,
                version_notes="Pinned YuE2 music + cover models and offline dependency wheels")
            print(f"Saved: https://www.kaggle.com/datasets/{DATASET_HANDLE}. Keep this dataset private.")
        """)]
    return {'cells': cells, 'metadata': {
        'kernelspec': {'display_name': 'Python 3', 'language': 'python', 'name': 'python3'},
        'language_info': {'name': 'python'},
        'kaggle': {'isGpuEnabled': False, 'isInternetEnabled': True},
    }, 'nbformat': 4, 'nbformat_minor': 4}


if __name__ == '__main__':
    output = ROOT / 'yue2-3b-frontier-full-song-music-generation.ipynb'
    output.write_text(json.dumps(build(), indent=1, ensure_ascii=False) + '\n')
    print(output)
    assets = ROOT / 'yue2-build-kaggle-assets.ipynb'
    assets.write_text(json.dumps(build_asset_notebook(), indent=1, ensure_ascii=False) + '\n')
    print(assets)
