"""TimestampStudio — ComfyUI node pack for Song Timestamp Studio.

A visible, connected canvas of real, individually executed nodes:

    LoadAudio ──▶ STS Align ◀── STS Lyrics & Options
                     │
        ┌────────────┼──────────────────┐
        ▼            ▼                  ▼
   STS Nudge   STS Audition ──AUDIO──▶ PreviewAudio
        │
        ▼
   STS Export All  (LRC / SRT / VTT / chapters / REAPER / beats / Cut Plan / JSON / ZIP)

The alignment engine is the standalone timestamp-studio engine (sts_engine.py,
written next to this file): Whisper listens to the song, then the KNOWN lyric
words are fuzzy-matched onto the words Whisper heard (forced alignment), so the
lyric text is always correct and only timing is measured. Beat grid and Cut Plan
come from librosa; the Cut Plan speaks seconds AND frames @ 24 fps.
"""
import os

os.environ.setdefault("STS_AUTOLAUNCH", "0")  # never auto-start the Gradio route here

import re
import shutil
import tempfile
import zipfile

import numpy as np

from . import sts_engine as engine

CATEGORY = "Song Timestamp Studio"
_PREF = "[TimestampStudio] "


def _safe_stem(name):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", str(name or "song")) or "song"
    return stem[:80]


def _audio_to_temp_wav(audio):
    """ComfyUI AUDIO dict -> mono WAV file path the engine can read."""
    import soundfile as sf

    waveform = audio["waveform"]
    sample_rate = int(audio.get("sample_rate", 44100))
    data = waveform.detach().cpu().numpy()
    if data.ndim == 3:  # [batch, channels, samples]
        data = data[0]
    if data.ndim == 2 and data.shape[0] > 1:  # stereo -> mono
        data = data.mean(axis=0)
    data = np.asarray(data, dtype=np.float32).reshape(-1)
    path = os.path.join(tempfile.gettempdir(), "sts_input_song.wav")
    sf.write(path, data, sample_rate)
    return path


def _result_summary(result):
    lines = len([e for e in result.get("entries", []) if e.get("kind") == "sing"])
    rate = result.get("match_rate")
    rate_text = f"{int(round(100 * rate))}% of lyric words located" if rate is not None else "auto-transcribed"
    bpm = result.get("bpm")
    bpm_text = f", ~{bpm:.1f} BPM" if bpm else ""
    return (f"✅ {lines} sung lines · {rate_text} · "
            f"{(result.get('duration') or 0):.1f}s{bpm_text}")


class STSLyricsOptions:
    """Lyrics you already wrote + engine choices. Empty lyrics = auto-transcribe."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "song_name": ("STRING", {"default": "my_song"}),
            "lyrics": ("STRING", {"default": engine.EXAMPLE_LYRICS, "multiline": True,
                                  "placeholder": "[Verse]\n...one line per row...\n\n[Chorus]\n..."}),
            "model": (engine.MODEL_CHOICES, {"default": "auto"}),
            "language": (engine.LANG_CHOICES, {"default": "auto"}),
            "isolate_vocals": ("BOOLEAN", {"default": False,
                                           "label_on": "on — dense mixes",
                                           "label_off": "off — clear mixes"}),
        }}

    RETURN_TYPES = ("STS_OPTS",)
    FUNCTION = "execute"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Paste the lyrics exactly as sung, one line per row. Keep your [Verse] / "
                   "[Chorus] tags: they become YouTube chapters and REAPER regions. Leave the "
                   "box EMPTY to auto-transcribe instead (text = what the AI hears).")

    def execute(self, song_name, lyrics, model, language, isolate_vocals):
        return ({"song_name": (song_name or "song").strip() or "song",
                 "lyrics": (lyrics or "").strip(),
                 "model": model, "language": language,
                 "isolate_vocals": bool(isolate_vocals)},)


class STSAlign:
    """Forced alignment: pins your known lyric lines onto exact seconds."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"audio": ("AUDIO",), "opts": ("STS_OPTS",)}}

    RETURN_TYPES = ("STS_RESULT",)
    FUNCTION = "execute"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True
    DESCRIPTION = ("Listens to the song and times every lyric line. First run downloads the "
                   "Whisper model (~150 MB, one-time per session). Confidence per line appears "
                   "in the Export node report; low scores → bigger model or vocal isolation.")

    def execute(self, audio, opts):
        import comfy.model_management as model_management

        model_management.throw_exception_if_processing_interrupted()
        path = _audio_to_temp_wav(audio)
        result = engine.run_alignment(
            path, opts["lyrics"], model_size=opts["model"], language=opts["language"],
            isolate_vocals_flag=opts["isolate_vocals"])
        result["song"] = opts["song_name"]
        result["nudge"] = 0.0
        print(_PREF + _result_summary(result), flush=True)
        return {"ui": {"text": [_result_summary(result)]}, "result": (result,)}


class STSNudge:
    """Shift every timestamp at once (early/late by a constant)."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "result": ("STS_RESULT",),
            "offset_seconds": ("FLOAT", {"default": 0.0, "min": -10.0, "max": 10.0,
                                         "step": 0.05}),
        }}

    RETURN_TYPES = ("STS_RESULT",)
    FUNCTION = "execute"
    CATEGORY = CATEGORY
    DESCRIPTION = ("If everything lands a constant amount early or late (long intro, slight "
                   "latency), nudge all timestamps at once. Audition and Export apply it too.")

    def execute(self, result, offset_seconds):
        shifted = dict(result)
        shifted["nudge"] = float(result.get("nudge", 0.0)) + float(offset_seconds or 0.0)
        print(_PREF + f"nudge now {shifted['nudge']:+.2f}s", flush=True)
        return (shifted,)


class STSAudition:
    """Play ~8 s of the song around one lyric line for a quick ear check."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {
            "result": ("STS_RESULT",),
            "line_number": ("INT", {"default": 1, "min": 1, "max": 999}),
            "lead_in_seconds": ("FLOAT", {"default": 1.5, "min": 0.0, "max": 5.0, "step": 0.1}),
        }}

    RETURN_TYPES = ("AUDIO",)
    FUNCTION = "execute"
    CATEGORY = CATEGORY
    DESCRIPTION = ("Wire into PreviewAudio. Plays from a moment before the chosen line so you "
                   "hear whether the vocal enters when the line fires. Nudged times apply.")

    def execute(self, result, line_number, lead_in_seconds):
        sing = [e for e in result.get("entries", []) if e.get("kind") == "sing"]
        if not sing:
            raise ValueError("No sung lines to audition — add lyrics or auto-transcribe first.")
        idx = int(max(1, min(int(line_number), len(sing)))) - 1
        t0 = max(0.0, sing[idx]["start"] + float(result.get("nudge", 0.0)) - float(lead_in_seconds))
        segment = np.asarray(result["audio_16k"][int(t0 * 16000): int((t0 + 8.0) * 16000)],
                             dtype=np.float32)
        import torch

        audio = {"waveform": torch.from_numpy(segment[None, None, :]),
                 "sample_rate": 16000}
        print(_PREF + f"audition line {idx + 1}/{len(sing)} from {t0:.2f}s", flush=True)
        return (audio,)


class STSExportAll:
    """Write every timestamp format into the ComfyUI output folder + one ZIP."""

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"result": ("STS_RESULT",)}}

    RETURN_TYPES = ()
    FUNCTION = "execute"
    CATEGORY = CATEGORY
    OUTPUT_NODE = True
    DESCRIPTION = ("Writes synced lyrics (LRC/SRT/VTT), YouTube chapters, REAPER markers CSV, "
                   "beat grid, beat-snapped Cut Plan (seconds + frames @ 24 fps), full JSON "
                   "and a README — plus one ZIP with everything, into the output folder.")

    def execute(self, result):
        import comfy.model_management as model_management

        model_management.throw_exception_if_processing_interrupted()
        try:
            import folder_paths

            out_root = folder_paths.get_output_directory()
        except Exception:
            out_root = os.environ.get("STS_OUTPUT_ROOT") or os.path.join(os.getcwd(), "output")
        stem = _safe_stem(result.get("song") or "song")
        nudge = float(result.get("nudge", 0.0))
        out_dir = os.path.join(out_root, f"{stem}_timestamps")
        os.makedirs(out_dir, exist_ok=True)

        zip_path = engine.build_zip(result, nudge)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()
            zf.extractall(out_dir)
        dest_zip = os.path.join(out_dir, os.path.basename(zip_path))
        if os.path.abspath(dest_zip) != os.path.abspath(zip_path):
            shutil.copyfile(zip_path, dest_zip)

        report = [f"✅ {len(names)} files → {out_dir}"]
        for name in names:
            report.append("   · " + name)
        report.append(f"   · {os.path.basename(dest_zip)} (everything in one ZIP)")
        if abs(nudge) >= 1e-6:
            report.append(f"nudge applied: {nudge:+.2f}s")
        preview = engine.render_outputs(result, nudge)["preview"]
        report.append("line check: " + " | ".join(
            f"{row[0]}:{row[4]}" for row in preview[:8]))
        report.append("REAPER audit: drag the _reaper_markers.csv into the Region/Marker "
                      "Manager (View menu) over your waveform.")
        text = "\n".join(report)
        print(_PREF + text, flush=True)
        return {"ui": {"text": [text]}, "result": ()}


NODE_CLASS_MAPPINGS = {cls.__name__: cls for cls in (
    STSLyricsOptions, STSAlign, STSNudge, STSAudition, STSExportAll)}

NODE_DISPLAY_NAME_MAPPINGS = {
    "STSLyricsOptions": "Lyrics & Options",
    "STSAlign": "Align Lyrics (forced alignment)",
    "STSNudge": "Nudge All Timestamps",
    "STSAudition": "Audition One Line",
    "STSExportAll": "Export All Formats + ZIP",
}

WEB_DIRECTORY = "./web"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
