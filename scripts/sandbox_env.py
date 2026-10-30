"""Sandbox deep-validation environment for the KaggleYuE2 ComfyUI pack.

Installs the yue2 stack + ComfyUI v0.43.2 exactly the way the notebook does:
- yue2_infer wheel (SHA-verified) with --no-deps, then its import deps
- pinned ComfyUI checkout + requirements under torch/transformers constraints
- the KaggleYuE2 node pack written via native_yue2.setup.write_comfy_pack
No model weights are downloaded; nothing GPU-related is executed.
"""
import hashlib
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

MUSIC = Path('/home/z/my-project/gh/Music')
SANDBOX = Path('/home/z/my-project/comfy_sandbox')
COMFY_DIR = SANDBOX / 'ComfyUI'
SUPPORT = SANDBOX / 'support'
COMFY_COMMIT = '423cbd20511becb1f16122ab518e92e58bfa03d9'  # v0.43.2
WHEEL_URL = ('https://huggingface.co/m-a-p/YuE2-3B/resolve/'
             '8f24312f187763b9854adeec87e437e2b03bbff1/yue2_infer-0.1.5-py3-none-any.whl')
WHEEL_SHA256 = '8801e2c0d969db02df78d2994150b4ccd86077d87c24fdb8509b1f6f31462641'


def run(args, **kwargs):
    print('>>', ' '.join(str(a) for a in args)[:160], flush=True)
    return subprocess.run([str(a) for a in args], check=True, **kwargs)


def pip(args):
    run([sys.executable, '-m', 'pip', 'install', '--quiet', *args])


def main():
    SANDBOX.mkdir(parents=True, exist_ok=True)
    SUPPORT.mkdir(parents=True, exist_ok=True)

    # 1. Support tree: native_yue2 + kaggle_yue2 exactly as the notebook extracts them.
    for pkg in ('native_yue2', 'kaggle_yue2'):
        dest = SUPPORT / pkg
        if dest.exists():
            subprocess.run(['rm', '-rf', str(dest)], check=True)
        subprocess.run(['cp', '-r', str(MUSIC / pkg), str(dest)], check=True)
    print('support tree ready at', SUPPORT)

    # 2. Engine-stack dependencies (gradio is imported by engine.py; the yue2
    #    wheel is installed --no-deps like the notebook does).
    pip(['torch==2.11.0', 'torchaudio==2.11.0',
         '--index-url', 'https://download.pytorch.org/whl/cpu'])
    pip(['torchvision', '--index-url', 'https://download.pytorch.org/whl/cpu'])
    pip(['transformers==4.57.6', 'huggingface-hub==0.36.2', 'tiktoken==0.12.0',
         'safetensors>=0.7.0', 'accelerate==1.13.0', 'soundfile==0.13.1',
         'gradio==5.49.1', 'pillow==11.3.0', 'scipy', 'mir_eval==0.8.2',
         'pretty_midi==0.2.10', 'mido==1.3.3'])

    wheel = SANDBOX / 'yue2_infer-0.1.5-py3-none-any.whl'
    if not wheel.is_file():
        with urllib.request.urlopen(WHEEL_URL, timeout=120) as response, wheel.open('wb') as out:
            out.write(response.read())
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    assert digest == WHEEL_SHA256, f'wheel checksum mismatch: {digest}'
    pip(['--no-deps', str(wheel)])

    # 3. Pinned ComfyUI checkout.
    if not (COMFY_DIR / '.git').exists():
        COMFY_DIR.mkdir(parents=True)
        run(['git', 'init', COMFY_DIR])
        run(['git', '-C', COMFY_DIR, 'remote', 'add', 'origin',
             'https://github.com/comfyanonymous/ComfyUI.git'])
    run(['git', '-C', COMFY_DIR, 'fetch', '--depth', '1', 'origin', COMFY_COMMIT])
    run(['git', '-C', COMFY_DIR, 'checkout', '--detach', 'FETCH_HEAD'])
    head = subprocess.run(['git', '-C', COMFY_DIR, 'rev-parse', 'HEAD'],
                          capture_output=True, text=True).stdout.strip()
    assert head == COMFY_COMMIT, head

    # 4. ComfyUI requirements under constraints (torch stack already CPU-pinned).
    constraints = SANDBOX / 'constraints.txt'
    torch_version = subprocess.run([sys.executable, '-c',
                                    'import torch; print(torch.__version__)'],
                                   capture_output=True, text=True).stdout.strip()
    tv_version = subprocess.run([sys.executable, '-c',
                                 'import torchvision; print(torchvision.__version__)'],
                                capture_output=True, text=True).stdout.strip()
    ta_version = subprocess.run([sys.executable, '-c',
                                 'import torchaudio; print(torchaudio.__version__)'],
                                capture_output=True, text=True).stdout.strip()
    constraints.write_text(f'torch=={torch_version}\ntorchvision=={tv_version}\n'
                           f'torchaudio=={ta_version}\ntransformers==4.57.6\n')
    run([sys.executable, '-m', 'pip', 'install', '--quiet',
         '-r', COMFY_DIR / 'requirements.txt', '-c', constraints])

    # 5. Write the KaggleYuE2 node pack through the real setup helper.
    sys.path.insert(0, str(SUPPORT))
    os.environ.setdefault('YUE2_SUPPORT_DIR', str(SUPPORT))
    from native_yue2.setup import write_comfy_pack, COMFYUI_COMMIT
    assert COMFYUI_COMMIT == COMFY_COMMIT
    pack = write_comfy_pack(COMFY_DIR)
    listing = sorted(str(p.relative_to(pack)) for p in pack.rglob('*') if p.is_file())
    print('node pack written:', json.dumps(listing, indent=1))
    assert 'web/yue2-song.json' in listing and 'web/yue2-cover.json' in listing
    assert 'web/open_workflow.js' in listing and '__init__.py' in listing
    print('SANDBOX ENV READY')


if __name__ == '__main__':
    main()
