#!/usr/bin/env python3
"""Launch the Timestamp Studio UI locally for browser verification."""
import os

os.environ["STS_AUTOLAUNCH"] = "0"
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import timestamp_studio as sts

demo = sts.build_ui()
demo.launch(
    server_name="127.0.0.1",
    server_port=7860,
    share=False,
    prevent_thread_lock=True,
    show_error=True,
    quiet=True,
    **sts._launch_theme(),
)
print("UI_UP_ON_7860", flush=True)
import time

time.sleep(1800)
