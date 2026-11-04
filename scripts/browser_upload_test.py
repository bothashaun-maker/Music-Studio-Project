#!/usr/bin/env python3
"""Real-browser test of the Song Timestamp Studio v2.0 upload flow.

One process does everything (the sandbox kills background processes between
tool calls, so nothing may depend on a previous call):

  1. start the sandbox ComfyUI server (with --max-upload-size 2048)
  2. browser tab A: /sts_uploader — pick a real file, watch the chunked
     uploader reach 100%, read the success message + song list
  3. browser tab B: /?sts_workflow=studio — the canvas loads with the
     STSLoadSong node; its combo must show the uploaded song
  4. back on tab A: upload a second song while tab B stays open — tab B's
     combo must gain it via BroadcastChannel WITHOUT a reload
  5. screenshots for the visual check
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("STS_AUTOLAUNCH", "0")

import test_sts_sandbox as sb

SANDBOX = "/home/z/my-project/comfy_sandbox"
COMFY = os.path.join(SANDBOX, "ComfyUI")
INPUTS = os.path.join(COMFY, "input")
PORT = 8189
BASE = f"http://127.0.0.1:{PORT}"
SHOTS = "/home/z/my-project/download/timestamp-studio-screens"
os.makedirs(SHOTS, exist_ok=True)

failures = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not cond:
        failures.append(name)


def make_wav(path, target_bytes, rate=8000):
    frames = max(rate, (target_bytes - 44) // 2)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        block = b"\x00" * (2 * rate)
        for _ in range(frames // rate):
            w.writeframes(block)
        w.writeframes(b"\x00" * (2 * (frames % rate)))
    pad = target_bytes - os.path.getsize(path)
    if pad > 0:
        with open(path, "ab") as f:
            f.write(b"\x00" * pad)


def wait_health(timeout=150):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE + "/sts/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(2)
    return False


CANVAS_CHECK = """() => {
    const app = window.app;
    if (!app || !app.graph) return JSON.stringify({error: 'no window.app / graph yet'});
    const node = (app.graph._nodes || []).find(n => n.type === 'STSLoadSong');
    if (!node) return JSON.stringify({error: 'STSLoadSong not on graph',
                                      types: (app.graph._nodes || []).map(n => n.type)});
    const w = (node.widgets || []).find(w => w.name === 'audio');
    return JSON.stringify({title: node.title, values: (w && w.options.values) || [],
                           value: w && w.value});
}"""


def main():
    sb.install_pack()  # fresh pack: never serve a stale extension
    big = os.path.join(SANDBOX, "browser_song_one.wav")
    second = os.path.join(SANDBOX, "browser_song_two.wav")
    make_wav(big, 18 * 1024 * 1024)
    make_wav(second, 3 * 1024 * 1024)

    log = open(os.path.join(SANDBOX, "server-browser.log"), "w")
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
         "--output-directory", os.path.join(SANDBOX, "sts_runs"), "--disable-auto-launch",
         "--cpu", "--max-upload-size", "2048"],
        cwd=COMFY, stdout=log, stderr=subprocess.STDOUT,
        env={**os.environ, "STS_SCAN_ROOTS": os.path.join(SANDBOX, "fake_kaggle")})
    try:
        check("server ready", wait_health())
        for f in ("browser_song_one.wav", "browser_song_two.wav"):
            p = os.path.join(INPUTS, f)
            if os.path.exists(p):
                os.remove(p)

        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(viewport={"width": 1440, "height": 960})
            up = ctx.new_page()
            up.add_init_script("""
              window.__msgs = [];
              new MutationObserver(() => {
                const e = document.getElementById('msg');
                if (e && window.__msgs[window.__msgs.length - 1] !== e.textContent)
                  window.__msgs.push(e.textContent);
              }).observe(document, {subtree: true, childList: true, characterData: true});
            """)
            up.goto(BASE + "/sts_uploader", timeout=60000)
            up.wait_for_timeout(1500)

            # -- 2 · upload the 18 MB song through the real file input ----------
            up.set_input_files("#file", big)
            up.wait_for_timeout(400)
            up.wait_for_selector("#msg.ok", timeout=120000)
            final_msg = up.inner_text("#msg")
            seen = " | ".join(up.evaluate("window.__msgs"))
            check("uploader ran the chunked flow (progress messages seen)",
                  ("piece" in seen or "%" in seen or "Uploading" in seen) and "100" in seen,
                  seen[-160:])
            check("uploader reached 100% with success message",
                  "browser_song_one.wav" in final_msg, final_msg[:140].replace("\n", " "))
            landed = os.path.join(INPUTS, "browser_song_one.wav")
            check("uploaded song really in ComfyUI input folder",
                  os.path.isfile(landed) and os.path.getsize(landed) == 18 * 1024 * 1024)
            check("songs list shows it as ready", "browser_song_one.wav" in up.inner_text("#songs"))
            up.screenshot(path=os.path.join(SHOTS, "uploader-after-upload.png"))

            # -- 3 · canvas tab: graph loads, node list carries the song --------
            cv = ctx.new_page()
            cv.goto(BASE + "/?sts_workflow=studio", timeout=60000)
            cv.wait_for_timeout(9000)  # mount + auto-open the studio canvas
            state = json.loads(cv.evaluate(CANVAS_CHECK))
            check("canvas loaded with the STSLoadSong node",
                  "error" not in state, json.dumps(state)[:220])
            if "error" not in state:
                check("song list on the node includes the uploaded song",
                      "browser_song_one.wav" in state.get("values", []),
                      json.dumps(state.get("values"))[:200])
                cv.wait_for_timeout(3500)  # let the settle-up guard re-sync the pick
                state = json.loads(cv.evaluate(CANVAS_CHECK))
                check("canvas auto-selected the uploaded song (no stale placeholder)",
                      state.get("value") == "browser_song_one.wav", str(state.get("value"))[:120])
            cv.screenshot(path=os.path.join(SHOTS, "canvas-with-your-song-node.png"))

            # -- 4 · second upload while the canvas tab is open -----------------
            up.bring_to_front()
            up.set_input_files("#file", second)
            up.wait_for_selector("#msg.ok", timeout=60000)
            cv.wait_for_timeout(1200)  # BroadcastChannel → combo refresh, no reload
            state2 = json.loads(cv.evaluate(CANVAS_CHECK))
            check("second song appears on the canvas node LIVE (no reload)",
                  "browser_song_two.wav" in state2.get("values", []),
                  json.dumps(state2.get("values"))[:200])
            cv.screenshot(path=os.path.join(SHOTS, "canvas-live-refresh.png"))

            browser.close()

        print("\n" + ("✅ BROWSER FLOW: all checks passed"
                      if not failures else f"❌ failed: {failures}"), flush=True)
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
