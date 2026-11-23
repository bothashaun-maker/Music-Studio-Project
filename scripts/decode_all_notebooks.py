"""General extractor: decode every code-cell payload of the music notebooks.

Writes the embedded sources to _inspect/decoded/<notebook>/... and prints a
generation matrix (which embedded copy of each source file matches which).
"""
import base64
import hashlib
import io
import json
import pathlib
import re
import zlib
import zipfile

BASE = pathlib.Path('/home/z/my-project/gh/Music-fix')
OUT = BASE / '_inspect' / 'decoded'

NOTEBOOKS = {
    'generator': 'yue2-3b-frontier-full-song-music-generation.ipynb',
    'rev15music': 'YuE2_Music_Revision15.ipynb',
    'assets': 'yue2-build-kaggle-assets.ipynb',
    'studio': 'Song-Timestamp-Studio-Canvas.ipynb',
    'comfy': 'YuE2_ComfyUI_Kaggle.ipynb',
    'musicstudio': 'Music-Studio.ipynb',
    'dataset': 'Music-Studio-Dataset.ipynb',
}

B64 = re.compile(r"['\"]([A-Za-z0-9+/=]{200,})['\"]")


def decode_payload(raw):
    """Return {posix_path: bytes} for a zip or zlib+json payload, else None."""
    packed = base64.b64decode(raw)
    try:
        with zipfile.ZipFile(io.BytesIO(packed)) as zf:
            return {name: zf.read(name) for name in zf.namelist() if not name.endswith('/')}
    except zipfile.BadZipFile:
        pass
    try:
        data = json.loads(zlib.decompress(packed))
    except Exception as error:
        return {'__ERROR__': repr(error).encode()}
    return {key: (value.encode() if isinstance(value, str) else value) for key, value in data.items()}


embedded = {}
for label, filename in NOTEBOOKS.items():
    nb = json.load(open(BASE / filename))
    found = {}
    for index, cell in enumerate(nb['cells']):
        if cell['cell_type'] != 'code':
            continue
        text = ''.join(cell['source'])
        for match in B64.finditer(text):
            files = decode_payload(re.sub(r'\s+', '', match.group(1)))
            for key, contents in files.items():
                found[key] = contents
                target = OUT / label / key.replace('\\', '/')
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
    embedded[label] = found
    bad = [k for k in found if '\\' in k]
    print(f'{label:12} {len(found):3} embedded files' + (f'  BACKSLASH KEYS: {len(bad)}' if bad else ''))

print('\n=== generation matrix (sha256 prefix per embedded file) ===')
all_keys = sorted({k.replace('\\', '/') for files in embedded.values() for k in files})
print(f'{"file":44} ' + ' '.join(f'{l:>10}' for l in NOTEBOOKS))
for key in all_keys:
    row = []
    for label in NOTEBOOKS:
        match = [v for k, v in embedded[label].items() if k.replace('\\', '/') == key]
        row.append(hashlib.sha256(match[0]).hexdigest()[:10] if match else '-')
    print(f'{key:44} ' + ' '.join(f'{c:>10}' for c in row))
