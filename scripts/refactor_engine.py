"""Refactor native_yue2/engine.py for importability by the ComfyUI node pack.

Two mechanical changes, sidecar behavior preserved byte-for-byte in effect:
1. Pipeline init (module-level) -> initialize_pipeline() + IS_MANAGED_ENGINE guard.
2. Gradio UI construction + launch (module-level) -> build_and_launch_ui() + guard.
"""
from pathlib import Path
import ast

TARGET = Path('/home/z/my-project/gh/Music/native_yue2/engine.py')
lines = TARGET.read_text().splitlines(keepends=True)

# ---- Refactor 1: lazy pipeline initialization --------------------------------
idx = next(i for i, l in enumerate(lines) if '# 2. Pipeline Initialization' in l)
start = idx - 1  # the '# ---' rule line above the header
end = next(i for i in range(idx, len(lines)) if lines[i].strip() == 'raise e')
block = lines[start:end + 1]
assert block[2].strip() == '# -----------------------------------------------------------------------------'
assert block[5].lstrip().startswith('print("\\nInitializing YuE2 pipeline')
assert block[6].strip() == 'try:'
assert block[7].strip().startswith('pipe = ypipe.YuE2Pipeline.from_pretrained(')

new_header = [
    '# -----------------------------------------------------------------------------\n',
    '# 2. Pipeline Initialization\n',
    '# -----------------------------------------------------------------------------\n',
    '# backend="torch" (not "torch-eager") is what enables the CUDA-graph AR decoder\n',
    '# in yue2/pipeline.py::_generate. Patch 3 keeps that path safe on Turing.\n',
    '# The managed engine script initializes at startup, exactly as before. Other\n',
    '# hosts (the ComfyUI node pack) import this module and call\n',
    '# initialize_pipeline() from their load node, so importing here loads no\n',
    '# weights, opens no UI and acquires no second engine lock.\n',
    'def initialize_pipeline():\n',
    '    global pipe\n',
]
body = []
for line in block[5:]:
    if line.strip() == 'pipe = ypipe.YuE2Pipeline.from_pretrained(':
        line = line.replace('pipe = ypipe.YuE2Pipeline', 'loaded = ypipe.YuE2Pipeline')
    elif 'VAE on {pipe.vae_device}' in line:
        line = line.replace('{pipe.vae_device}', '{loaded.vae_device}')
    body.append(('    ' + line) if line.strip() else line)
body += [
    '    pipe = loaded\n',
    '    return pipe\n',
]
tail1 = [
    '\n',
    'pipe = None  # Set by initialize_pipeline(); the managed engine calls it below.\n',
    'if IS_MANAGED_ENGINE:\n',
    '    initialize_pipeline()\n',
]
lines[start:end + 1] = new_header + body + tail1

# ---- Refactor 2: guard the Gradio UI -----------------------------------------
ui_start = next(i for i, l in enumerate(lines) if '# 5. AIQUEST Academy Modern Gradio UI' in l)
ui_start -= 1  # the '# ---' rule line above the header
ui_block = lines[ui_start:]
assert ui_block[0].strip() == '# -----------------------------------------------------------------------------'
assert ui_block[-1].strip().startswith('demo.queue(default_concurrency_limit=1).launch(')

# No multiline gr.Markdown templates may suffer markdown code-block reindenting.
text = ''.join(ui_block)
assert 'gr.Markdown("""' not in text, 'Multiline markdown would be damaged by reindent'

wrapped = ['\n', '# -----------------------------------------------------------------------------\n',
           '# 5. AIQUEST Academy Modern Gradio UI\n', '# -----------------------------------------------------------------------------\n',
           '# Built and launched only by the managed engine process. The ComfyUI node\n',
           '# pack imports this module for the pipeline; it never builds this UI.\n',
           'def build_and_launch_ui():\n']
wrapped += [('    ' + l if l.strip() else l) for l in ui_block[3:]]
wrapped += ['\n', '\n', 'if IS_MANAGED_ENGINE:\n', '    build_and_launch_ui()\n']
lines[ui_start:] = wrapped

TARGET.write_text(''.join(lines))

# ---- Verify: syntax + structure ---------------------------------------------
source = TARGET.read_text()
ast.parse(source)
compile(source, 'engine.py', 'exec')
assert 'def initialize_pipeline():' in source
assert 'def build_and_launch_ui():' in source
assert source.count('    initialize_pipeline()') == 1  # the managed call
assert source.count('    build_and_launch_ui()') == 1
print('engine.py refactor OK:',
      len(source.splitlines()), 'lines;',
      'pipeline lazy, UI guarded.')
