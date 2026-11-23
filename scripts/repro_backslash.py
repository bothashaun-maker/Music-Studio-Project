"""Reproduce the Music-Studio.ipynb support-file extraction on Linux.

Runs the notebook cell's own extraction loop verbatim (payload -> support dir),
then proves that `python -m music_studio.launch` cannot import the package.
Usage: python repro_backslash.py <repo_root> <out_root>
"""
import base64
import hashlib
import json
import os
import subprocess
import sys
import zlib
from pathlib import Path

REPO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
NOTEBOOK = REPO / 'Music-Studio.ipynb'

cell = json.loads(NOTEBOOK.read_text())['cells'][1]
code = ''.join(cell['source'])

# Extract the payload exactly as the cell does.
marker = "packed = base64.b64decode("
encoded = code.split(marker, 1)[1].split("\n", 1)[0].strip()
encoded = encoded[:encoded.rindex("'") + 1].strip("'\"")
packed = base64.b64decode(encoded)
print('payload sha256:', hashlib.sha256(packed).hexdigest())
keys = list(json.loads(zlib.decompress(packed)))
print('payload keys (verbatim):')
for k in keys:
    print('   ', repr(k))

support = OUT / '.music_studio_support' / '90f19fbc9801'
support.mkdir(parents=True, exist_ok=True)
# The notebook's own loop, unchanged:
for relative, contents in json.loads(zlib.decompress(packed)).items():
    path = support / relative
    if not path.resolve().is_relative_to(support.resolve()):
        raise RuntimeError('Invalid embedded source path')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents)

print('\nFiles actually written under', support)
for p in sorted(support.rglob('*')):
    print('   ', p.relative_to(support), '(dir)' if p.is_dir() else f'({p.stat().st_size} B)')

env = dict(os.environ)
env['PYTHONPATH'] = str(support) + os.pathsep + env.get('PYTHONPATH', '')
env['PYTHONUNBUFFERED'] = '1'
print('\nPYTHONPATH for the launch subprocess:', env['PYTHONPATH'])
result = subprocess.run([sys.executable, '-c', 'import music_studio.launch as m; print("import OK:", m.__file__)'],
                        env=env, capture_output=True, text=True)
print('import music_studio.launch ->', 'OK' if result.returncode == 0 else 'FAILED')
print(result.stdout[-500:])
print(result.stderr[-1500:])
sys.exit(0 if result.returncode == 0 else 1)
