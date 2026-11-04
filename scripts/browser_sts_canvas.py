#!/usr/bin/env python3
"""Browser check: the Timestamp Studio canvas auto-loads from ?sts_workflow=studio
in the real pinned ComfyUI browser, with no page errors and no missing nodes."""
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
PORT = 8189
BASE = f"http://127.0.0.1:{PORT}"
SHOT = "/home/z/my-project/download/timestamp-studio-screens/canvas_loaded.png"
os.makedirs(os.path.dirname(SHOT), exist_ok=True)

from test_sts_sandbox import install_pack  # reuse the exact same pack install

failures = []


def check(name, cond, detail=""):
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""), flush=True)
    if not cond:
        failures.append(name)


def main():
    install_pack()
    outputs = os.path.join(SANDBOX, "sts_runs")
    log = open(os.path.join(SANDBOX, "sts-server.log"), "w")
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py", "--listen", "127.0.0.1", "--port", str(PORT),
         "--output-directory", outputs, "--disable-auto-launch", "--cpu"],
        cwd=COMFY, stdout=log, stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 180
        ready = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(BASE + "/system_stats", timeout=3) as r:
                    ready = r.status == 200
                    if ready:
                        break
            except Exception:
                time.sleep(1.5)
        check("server ready for browser audit", ready)
        info = json.loads(urllib.request.urlopen(BASE + "/object_info", timeout=30).read().decode())
        check("STS nodes served before browser opens",
              all(n in info for n in ("STSLyricsOptions", "STSAlign", "STSNudge", "STSAudition", "STSExportAll")))

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 2200, "height": 1100})
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.on("dialog", lambda d: (errors.append(d.message), d.dismiss()))
            page.goto(BASE + "/?sts_workflow=studio", wait_until="networkidle")
            page.wait_for_function("window.app?.graph?._nodes?.length === 7", timeout=60000)
            page.wait_for_timeout(3000)
            nodes = page.evaluate("app.graph._nodes.length")
            types = page.evaluate("app.graph._nodes.map(n => n.type)")
            check("canvas auto-loaded 7 nodes from the link", nodes == 7, str(types))
            check("all 5 STS nodes on the graph",
                  all(t in types for t in ("STSLyricsOptions", "STSAlign", "STSNudge", "STSAudition", "STSExportAll")))
            check("link parameter stripped after load", "sts_workflow" not in page.url)
            check("no page errors / dialogs", not errors, str(errors[:2]))
            page.keyboard.press("Escape")
            page.screenshot(path=SHOT)
            print("screenshot:", SHOT, flush=True)
            # refresh must not re-fetch the template (edits preserved)
            page.reload(wait_until="domcontentloaded")
            page.wait_for_function("window.app?.graph?._nodes?.length === 7", timeout=60000)
            check("refresh keeps the graph", page.evaluate("app.graph._nodes.length") == 7)
            browser.close()
        print("\n" + ("✅ BROWSER AUDIT: all checks passed" if not failures else f"❌ failed: {failures}"), flush=True)
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
