"""Extract code cells from the Music Studio notebooks for inspection."""
import json
import pathlib

BASE = pathlib.Path('/home/z/my-project/gh/Music-fix')
OUT = BASE / '_inspect'
OUT.mkdir(exist_ok=True)

for name in ('Music-Studio-Dataset', 'Music-Studio', 'YuE2_ComfyUI_Kaggle'):
    nb = json.load(open(BASE / f'{name}.ipynb'))
    for i, cell in enumerate(nb['cells']):
        if cell['cell_type'] != 'code':
            continue
        src = ''.join(cell['source'])
        target = OUT / f'{name}-cell{i}.py'
        target.write_text(src)
        print(target, len(src.splitlines()), 'lines')
