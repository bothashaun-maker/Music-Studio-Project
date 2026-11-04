#!/usr/bin/env python3
"""Package Music revision 12 + the Timestamp Studio canvas notebook."""
import os
import shutil
import zipfile

DL = "/home/z/my-project/download"
REPO = "/home/z/my-project/gh/Music"

# 1 · notebooks to download/
for name in ("yue2-3b-frontier-full-song-music-generation.ipynb",
             "yue2-build-kaggle-assets.ipynb"):
    shutil.copyfile(os.path.join(REPO, name), os.path.join(DL, name))
    print("copied:", name)

# 2 · timestamp studio canvas zip
zip_path = os.path.join(DL, "Song-Timestamp-Studio-Canvas.zip")
with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    zf.write(os.path.join(DL, "Song-Timestamp-Studio-Canvas.ipynb"),
             "Song-Timestamp-Studio-Canvas.ipynb")
    zf.write("/home/z/my-project/scripts/archive/READ-ME-FIRST-canvas.md", "READ-ME-FIRST.md")
print("wrote:", zip_path, f"{os.path.getsize(zip_path) / 1024:.1f} KB")

# 3 · full Music repo revision 12 zip
repo_zip = os.path.join(DL, "yue2-music-revision-12.zip")
skip_dirs = {"__pycache__", ".git", ".ipynb_checkpoints"}
with zipfile.ZipFile(repo_zip, "w", zipfile.ZIP_DEFLATED) as zf:
    count = 0
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in skip_dirs]
        for f in files:
            full = os.path.join(root, f)
            zf.write(full, os.path.relpath(full, REPO))
            count += 1
print("wrote:", repo_zip, f"{os.path.getsize(repo_zip) / 1024:.1f} KB,", count, "files")
