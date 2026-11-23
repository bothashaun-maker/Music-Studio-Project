"""Decode embedded payloads from Music Studio / Comfy canvas notebooks into readable source."""
import base64
import json
import pathlib
import re
import zlib

BASE = pathlib.Path('/home/z/my-project/gh/Music-fix')
OUT = BASE / '_inspect' / 'decoded'
OUT.mkdir(parents=True, exist_ok=True)

# Music-Studio-Dataset: base64 ZIP payload
nb = json.load(open(BASE / 'Music-Studio-Dataset.ipynb'))
src = ''.join(nb['cells'][1]['source'])
m = re.search(r"base64\.b64decode\('([A-Za-z0-9+/=]+)'\)", src)
zip_payload = base64.b64decode(m.group(1))
print('dataset payload sha256:', __import__('hashlib').sha256(zip_payload).hexdigest())

import io
import zipfile
with zipfile.ZipFile(io.BytesIO(zip_payload)) as zf:
    for name in zf.namelist():
        target = OUT / 'dataset' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(zf.read(name))
        print('  extracted', name, zf.getinfo(name).file_size, 'bytes')

# Music-Studio + YuE2_ComfyUI_Kaggle: zlib-packed JSON dicts
for name in ('Music-Studio', 'YuE2_ComfyUI_Kaggle'):
    nb = json.load(open(BASE / f'{name}.ipynb'))
    src = ''.join(nb['cells'][1]['source'])
    m = re.search(r"base64\.b64decode\('([A-Za-z0-9+/=]+)'\)", src)
    if not m:
        print(name, ': no payload found')
        continue
    packed = base64.b64decode(m.group(1))
    print(name, 'payload sha256:', __import__('hashlib').sha256(packed).hexdigest())
    data = json.loads(zlib.decompress(packed))
    for rel, contents in data.items():
        target = OUT / name / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(contents)
        print('  extracted', rel, len(contents), 'chars')
