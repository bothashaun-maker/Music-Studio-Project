#!/usr/bin/env python3
"""Build the full chat + files archive zip the user ordered."""
import os
import zipfile

DL = "/home/z/my-project/download"
OUT = os.path.join(DL, "FULL-CHAT-AND-ALL-FILES.zip")

items = [
    ("FULL_CHAT_LOG.md", "FULL_CHAT_LOG.md"),
    ("DELIVERY-revision-15.md", "DELIVERY-revision-15.md"),
    ("Song-Timestamp-Studio-Canvas.zip", "Song-Timestamp-Studio-Canvas.zip"),
    ("Song-Timestamp-Studio-Canvas.ipynb", "Song-Timestamp-Studio-Canvas.ipynb"),
    ("yue2-music-revision-15.zip", "yue2-music-revision-15.zip"),
    ("yue2-3b-frontier-full-song-music-generation.ipynb", "yue2-3b-frontier-full-song-music-generation.ipynb"),
    ("yue2-build-kaggle-assets.ipynb", "yue2-build-kaggle-assets.ipynb"),
    ("song-timestamp-toolkit.pdf", "song-timestamp-toolkit.pdf"),
    ("song-timestamp-toolkit.html", "song-timestamp-toolkit.html"),
]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zf:
    for src, arc in items:
        p = os.path.join(DL, src)
        if os.path.isfile(p):
            zf.write(p, arc)
            print("added file:", arc)
        else:
            print("MISSING:", src)

    # browser-test screenshots of the v2.0 flow
    shots = os.path.join(DL, "timestamp-studio-screens")
    if os.path.isdir(shots):
        for f in sorted(os.listdir(shots)):
            zf.write(os.path.join(shots, f), os.path.join("timestamp-studio-screens", f))
        print("added screenshots:", len(os.listdir(shots)))

    # full repo sources, excluding caches
    skip_dirs = {"__pycache__", ".git", ".ipynb_checkpoints", "node_modules"}
    for repo, arcdir in (("/home/z/my-project/gh/Music", "Music-repo"),
                         ("/home/z/my-project/gh/Movies", "Movies-repo")):
        for root, dirs, files in os.walk(repo):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.join(arcdir, os.path.relpath(full, repo))
                zf.write(full, arc)
        print("added repo:", arcdir)

print("wrote:", OUT, f"{os.path.getsize(OUT) / 1e6:.1f} MB")
