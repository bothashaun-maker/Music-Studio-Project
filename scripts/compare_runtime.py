"""Compare embedded runtime.py across notebooks + check model pack builder payload keys."""
import base64
import hashlib
import json
import pathlib
import re
import zipfile
import io
import zlib

BASE = pathlib.Path('/home/z/my-project/gh/Music-fix')
OUT = BASE / '_inspect' / 'decoded'

def embedded_sources(nb_path):
    nb = json.load(open(nb_path))
    text = ''.join(nb['cells'][1]['source']) if nb['cells'][1]['cell_type'] == 'code' else ''
    return text

# 1. Extract runtime.py embedded in the working generator notebook (root, origin/main)
gen = BASE / 'yue2-3b-frontier-full-song-music-generation.ipynb'
nb = json.load(open(gen))
text = ''.join(nb['cells'][1]['source'])
print('generator notebook: code cells =', sum(1 for c in nb['cells'] if c['cell_type'] == 'code'),
      'total cells =', len(nb['cells']))
gen_dir = OUT / 'generator'
gen_dir.mkdir(parents=True, exist_ok=True)
# find b64 payload (zip) in generator notebook
m = re.search(r"base64\.b64decode\(\s*'([A-Za-z0-9+/=\s]+)'", text, re.S)
if m:
    raw = re.sub(r'\s+', '', m.group(1))
    payload = base64.b64decode(raw)
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            if name.endswith(('.py', '.txt', '.json')):
                target = gen_dir / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(zf.read(name))
        print('generator payload entries:', len(zf.namelist()))
        runtime_gen = gen_dir / 'kaggle_yue2' / 'runtime.py'
        print('generator runtime.py exists:', runtime_gen.exists())
else:
    print('no zip payload found in generator notebook; showing cell head')
    for line in text.splitlines()[:12]:
        print('   ', line[:120])

# 2. Model Pack Builder payload keys
mp = BASE / 'music_studio' / 'Music_Studio_Model_Pack_Builder.ipynb'
nb = json.load(open(mp))
print('\nModel Pack Builder cells:', len(nb['cells']))
for i, cell in enumerate(nb['cells']):
    src = ''.join(cell['source'])
    head = src.strip().splitlines()[0][:100] if src.strip() else '(empty)'
    print(f'  cell {i} [{cell["cell_type"]}] {len(src)} chars: {head}')
    if cell['cell_type'] == 'code':
        m = re.search(r"base64\.b64decode\('([A-Za-z0-9+/=]+)'\)", src)
        if m:
            payload = base64.b64decode(m.group(1))
            print('    payload sha256:', hashlib.sha256(payload).hexdigest())
            try:
                data = json.loads(zlib.decompress(payload))
                for key in data:
                    print('    key:', repr(key))
            except Exception:
                with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                    for name in zf.namelist():
                        print('    zip entry:', name)
