#!/usr/bin/env python3
"""Run the notebook's app cell exactly as Kaggle would (STS_AUTOLAUNCH=1),
capture the printed links, then exit. Simulates what the user sees."""
import json
import re
import subprocess
import sys

NB = "/home/z/my-project/download/song-timestamp-studio.ipynb"
cells = ["".join(c["source"]) for c in json.load(open(NB))["cells"]]
app_cell = next(c for c in cells if "def start_cloudflare" in c)

# Run in a fresh interpreter, like a notebook kernel, with a hard timeout.
proc = subprocess.Popen(
    [sys.executable, "-c", app_cell],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd="/home/z/my-project/scripts")
try:
    out, _ = proc.communicate(timeout=150)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()

gradio_links = re.findall(r"https://[a-z0-9-]+\.gradio\.live", out)
cf_links = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", out)
print("--- launch output (tail) ---")
print("\n".join(out.splitlines()[-14:]))
print("--- verification ---")
print("gradio.live link printed:", bool(gradio_links), gradio_links[:1])
print("trycloudflare link printed:", bool(cf_links), cf_links[:1])
print("crashed:", proc.returncode not in (0, None) and "Traceback" in out)
ok = bool(gradio_links) and bool(cf_links)
print("KAGGLE_LAUNCH_SIMULATION:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
