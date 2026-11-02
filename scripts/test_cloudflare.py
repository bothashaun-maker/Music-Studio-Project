#!/usr/bin/env python3
"""Live test: launch the studio UI locally, then open a real Cloudflare tunnel."""
import os
import sys

os.environ["STS_AUTOLAUNCH"] = "0"
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import timestamp_studio as sts  # noqa: E402

demo = sts.build_ui()
demo.launch(server_name="127.0.0.1", server_port=7861, share=False,
            prevent_thread_lock=True, quiet=True, show_error=True)
print("local UI up on 7861", flush=True)

try:
    url = sts.start_cloudflare(7861, timeout=90)
    print("CLOUDFLARE_URL:", url, flush=True)
    # verify the tunnel actually serves the app
    import time
    import urllib.request
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                body = r.read(2000).decode("utf-8", "replace")
            ok = "gradio" in body.lower() or "<!doctype html" in body.lower()
            print("TUNNEL_SERVES_APP:", ok, "| bytes:", len(body), flush=True)
            break
        except Exception as exc:
            print(f"probe {attempt + 1} failed: {exc}", flush=True)
            time.sleep(3)
    else:
        print("TUNNEL_SERVES_APP: FAILED (all probes)", flush=True)
except Exception as exc:
    print("CLOUDFLARE_FAILED:", type(exc).__name__, str(exc)[:400], flush=True)

import time  # noqa: E402
time.sleep(2)
os._exit(0)
