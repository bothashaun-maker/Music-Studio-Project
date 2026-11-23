"""Deep-inspect notebook payloads: comfy canvas decode + path-key verification."""
import base64
import hashlib
import json
import pathlib
import re
import zlib

BASE = pathlib.Path('/home/z/my-project/gh/Music-fix')
OUT = BASE / '_inspect' / 'decoded'
INSPECT = BASE / '_inspect'

# --- 1. Verify Music-Studio JSON keys (backslash suspicion) ---
nb = json.load(open(BASE / 'Music-Studio.ipynb'))
src = ''.join(nb['cells'][1]['source'])
m = re.search(r"base64\.b64decode\('([A-Za-z0-9+/=]+)'\)", src)
packed = base64.b64decode(m.group(1))
data = json.loads(zlib.decompress(packed))
print('=== Music-Studio payload keys (repr) ===')
for key in data:
    print(' ', repr(key))

# --- 2. YuE2_ComfyUI_Kaggle: show cell lines without dumping the payload ---
cell = (INSPECT / 'YuE2_ComfyUI_Kaggle-cell1.py').read_text()
lines = cell.splitlines()
print('\n=== YuE2_ComfyUI_Kaggle cell structure ===')
for i, line in enumerate(lines, 1):
    if len(line) > 200:
        print(f'  line {i}: <{len(line)} chars of base64-like data>')
    else:
        print(f'  line {i}: {line}')

# --- 3. Decode the comfy canvas payload ---
blob = ''.join(lines)  # join all lines, then find the longest b64 run
m2 = re.search(r"['\"]{1,3}([A-Za-z0-9+/=\s]{1000,})['\"]{1,3}", blob)
if not m2:
    # maybe the payload is assembled from chunks; look for assignments
    print('\nNo single big b64 literal; checking for chunked assembly')
    for i, line in enumerate(lines, 1):
        if re.fullmatch(r"[A-Za-z0-9+/=]{50,}", line.strip()):
            print(f'  line {i} looks like pure b64 chunk ({len(line)} chars)')
else:
    raw = re.sub(r'\s+', '', m2.group(1))
    packed = base64.b64decode(raw)
    print('\ncomfy payload sha256:', hashlib.sha256(packed).hexdigest())
    try:
        data = json.loads(zlib.decompress(packed))
        print('zlib+json OK, keys:')
        for key in data:
            print(' ', repr(key), len(data[key]), 'chars')
        for key, contents in data.items():
            rel = key.replace('\\', '/')
            target = OUT / 'comfy' / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(contents)
    except Exception as error:
        print('zlib/json failed:', error)
        # try plain zip
        import io
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(packed)) as zf:
                print('It is a ZIP with', len(zf.namelist()), 'entries')
                for name in zf.namelist():
                    print('  ', name)
                    target = OUT / 'comfy' / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(zf.read(name))
        except Exception as error2:
            print('zip failed too:', error2)
