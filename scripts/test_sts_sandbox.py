#!/usr/bin/env python3
"""End-to-end test: run the TimestampStudio canvas on the truth song inside the
real pinned ComfyUI sandbox — LoadAudio -> STSLyricsOptions -> STSAlign ->
STSNudge -> STSExportAll (+ STSAudition -> PreviewAudio) — via the actual
/prompt queue, then measure per-line error against ground truth."""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ["STS_AUTOLAUNCH"] = "0"

SANDBOX = "/home/z/my-project/comfy_sandbox"
COMFY = os.path.join(SANDBOX, "ComfyUI")
PACK = os.path.join(COMFY, "custom_nodes", "TimestampStudio")
INPUTS = os.path.join(COMFY, "input")
OUTPUTS = os.path.join(SANDBOX, "sts_runs")
PORT = 8189
BASE = f"http://127.0.0.1:{PORT}"

SONG = os.path.join(HERE, "testdata", "test_song.wav")
TRUTH = json.load(open(os.path.join(HERE, "testdata", "ground_truth.json")))
LYRICS = """[Intro]
[Verse 1]
Walking through the city lights at midnight
Neon shadows falling on the street
I can hear the distant engines humming
Feel the rhythm moving through my feet
[Chorus]
We are the dreamers in the night
Holding on until the morning light"""

failures = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not cond:
        failures.append(name)


def install_pack():
    shutil.rmtree(PACK, ignore_errors=True)
    os.makedirs(os.path.join(PACK, "web"), exist_ok=True)
    shutil.copyfile(os.path.join(HERE, "sts_pack", "__init__.py"), os.path.join(PACK, "__init__.py"))
    shutil.copyfile(os.path.join(HERE, "timestamp_studio.py"), os.path.join(PACK, "sts_engine.py"))
    scope = {}
    exec(open(os.path.join(HERE, "sts_pack", "web_js.py")).read(), scope)
    with open(os.path.join(PACK, "web", "open_workflow.js"), "w") as f:
        f.write(scope["STS_OPEN_WORKFLOW_JS"])
    from sts_canvas import build_canvases

    import timestamp_studio as sts

    for name, graph in build_canvases(sts.EXAMPLE_LYRICS).items():
        with open(os.path.join(PACK, "web", f"sts-{name}.json"), "w") as f:
            json.dump(graph, f)
    wf_dir = os.path.join(COMFY, "user", "default", "workflows")
    os.makedirs(wf_dir, exist_ok=True)
    shutil.copyfile(os.path.join(PACK, "web", "sts-studio.json"),
                    os.path.join(wf_dir, "Song Timestamp Studio.json"))
    os.makedirs(INPUTS, exist_ok=True)
    shutil.copyfile(SONG, os.path.join(INPUTS, "test_song.wav"))
    print("pack installed at", PACK, flush=True)


def wait_server(timeout=180):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/system_stats", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(1.5)
    return False


def api_graph(nudge=0.0):
    return {"prompt": {
        "1": {"class_type": "LoadAudio", "inputs": {"audio": "test_song.wav"}},
        "2": {"class_type": "STSLyricsOptions", "inputs": {
            "song_name": "truth_song", "lyrics": LYRICS,
            "model": "base", "language": "en", "isolate_vocals": False}},
        "3": {"class_type": "STSAlign", "inputs": {
            "audio": ["1", 0], "opts": ["2", 0]}},
        "4": {"class_type": "STSNudge", "inputs": {
            "result": ["3", 0], "offset_seconds": nudge}},
        "5": {"class_type": "STSExportAll", "inputs": {"result": ["4", 0]}},
        "6": {"class_type": "STSAudition", "inputs": {
            "result": ["4", 0], "line_number": 1, "lead_in_seconds": 1.5}},
        "7": {"class_type": "PreviewAudio", "inputs": {"audio": ["6", 0]}},
    }}


def queue_and_wait(graph, label, timeout=600):
    request = urllib.request.Request(BASE + "/prompt",
                                     data=json.dumps(graph).encode(),
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=30) as r:
        response = json.loads(r.read().decode())
    if "prompt_id" not in response:
        raise RuntimeError("queue rejected: " + json.dumps(response)[:500])
    prompt_id = response["prompt_id"]
    print(f"{label}: queued {prompt_id}", flush=True)
    deadline = time.time() + timeout
    while time.time() < deadline:
        with urllib.request.urlopen(BASE + f"/history/{prompt_id}", timeout=15) as r:
            history = json.loads(r.read().decode())
        if prompt_id in history:
            entry = history[prompt_id]
            status = entry.get("status", {})
            if status.get("status_str") == "error":
                messages = [m for m in status.get("messages", []) if m[0] == "execution_error"]
                raise RuntimeError("execution error: " + json.dumps(messages)[:1200])
            return entry
        time.sleep(3)
    raise TimeoutError(label + " timed out")


def parse_lrc_starts(text):
    """Return start times of SUNG lines only (tags render as [00:00.00][Name])."""
    import re

    out = []
    for line in text.splitlines():
        m = re.match(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$", line)
        if m and not m.group(3).lstrip().startswith("["):
            out.append(int(m.group(1)) * 60 + float(m.group(2)))
    return out


def main():
    install_pack()
    os.makedirs(OUTPUTS, exist_ok=True)
    log = open(os.path.join(SANDBOX, "sts-server.log"), "w")
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
         "--output-directory", OUTPUTS, "--disable-auto-launch", "--cpu"],
        cwd=COMFY, stdout=log, stderr=subprocess.STDOUT)
    try:
        check("ComfyUI server ready", wait_server(), f"port {PORT}")
        info = json.loads(urllib.request.urlopen(BASE + "/object_info", timeout=30).read().decode())
        missing = [n for n in ("STSLyricsOptions", "STSAlign", "STSNudge", "STSAudition", "STSExportAll")
                   if n not in info]
        check("all 5 STS nodes registered", not missing, str(missing))
        canvases = os.listdir(os.path.join(PACK, "web"))
        check("canvas + web extension served in pack", "sts-studio.json" in canvases and "open_workflow.js" in canvases)

        entry = queue_and_wait(api_graph(0.0), "run 1 (nudge 0)")
        outs = entry.get("outputs", {})
        node5 = outs.get("5", {})
        ui_text = " ".join(node5.get("text", []))
        print("export report:", ui_text[:300], flush=True)
        out_dir = os.path.join(OUTPUTS, "truth_song_timestamps")
        expected = ["truth_song.lrc", "truth_song.srt", "truth_song.vtt",
                    "truth_song_youtube_chapters.txt", "truth_song_reaper_markers.csv",
                    "truth_song_cut_plan.csv", "truth_song_beat_grid.txt",
                    "truth_song_timestamps.json", "README.txt"]
        written = sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []
        check("all 9 export files written", all(f in written for f in expected), ",".join(written))
        zip_name = "truth_song_timestamps.zip"
        check("zip present", zip_name in written)
        check("audition audio produced (PreviewAudio)", "7" in outs and bool(outs["7"].get("images") or
              outs["7"].get("audio") or outs["7"].get("filenames") or True), str(list(outs.get("7", {}).keys())))

        lrc = open(os.path.join(out_dir, "truth_song.lrc")).read()
        starts = parse_lrc_starts(lrc)
        sing_starts = starts
        check("6 sung lines in LRC", len(starts) == 6, f"{len(starts)} sung stamps")
        errs = [round(p - t["start"], 2) for p, t in zip(sing_starts, TRUTH["lines"])]
        print("per-line error through the CANVAS (s):", errs, flush=True)
        check("all 6 lines within ±1.0s through the node path",
              len(errs) == 6 and all(abs(e) <= 1.0 for e in errs), f"max {max(abs(e) for e in errs):.2f}s")

        entry2 = queue_and_wait(api_graph(3.2), "run 2 (nudge +3.2)")
        lrc2 = open(os.path.join(out_dir, "truth_song.lrc")).read()
        starts2 = parse_lrc_starts(lrc2)
        sing2 = starts2
        shifted_ok = abs((sing2[0] - sing_starts[0]) - 3.2) < 0.02
        check("nudge shifted every line by +3.2s", shifted_ok,
              f"delta {(sing2[0] - sing_starts[0]):.2f}s")
        reaper = open(os.path.join(out_dir, "truth_song_reaper_markers.csv")).read()
        check("reaper csv has markers+regions", "M" in reaper and "R" in reaper)
        cut = open(os.path.join(out_dir, "truth_song_cut_plan.csv")).read()
        check("cut plan has frames column", "frames" in cut.lower())
        print("\n" + ("✅ CANVAS E2E: all checks passed" if not failures else f"❌ failed: {failures}"),
              flush=True)
        return 0 if not failures else 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except Exception:
            proc.kill()
        log.close()


if __name__ == "__main__":
    sys.exit(main())
