"""Integration validation: real ComfyUI server + KaggleYuE2 pack.

1. Launch the server exactly like the notebook cell does (same flags/env shape).
2. Verify /object_info registers every KaggleYuE2 node with expected inputs.
3. Verify the web extension + both canvas JSONs are served.
4. Convert both canvases to API-prompt format and POST /prompt so ComfyUI's own
   validator judges the graphs (queue interrupted immediately afterwards).
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SANDBOX = Path('/home/z/my-project/comfy_sandbox')
COMFY_DIR = SANDBOX / 'ComfyUI'
SUPPORT = SANDBOX / 'support'
PORT = 8188
OUTPUTS = SANDBOX / 'runs'

env = dict(os.environ)
env.update({
    'YUE2_SUPPORT_DIR': str(SUPPORT),
    'YUE2_ENGINE_SCRIPT': str(SUPPORT / 'native_yue2' / 'engine.py'),
    'YUE2_RUNTIME_ROOT': str(SANDBOX / 'runtime'),
    'YUE2_OUTPUT_ROOT': str(OUTPUTS),
    'YUE2_NATIVE_ATTENTION': 'efficient_grouped',
})
OUTPUTS.mkdir(parents=True, exist_ok=True)

EXPECTED_NODES = {
    'YuE2RunContext': {'required': ['seed'], 'outputs': ['YUE2_RUN']},
    'YuE2LoadEngine': {'required': ['run'], 'optional': ['keep_loaded'], 'outputs': ['YUE2_ENGINE']},
    'YuE2StyleLyrics': {'required': ['style', 'lyrics'], 'outputs': ['YUE2_PROMPT']},
    'YuE2PlanScore': {'required': ['run', 'engine', 'prompt', 'planning_mode', 'cfg_scale'],
                      'outputs': ['YUE2_PLAN']},
    'YuE2CustomABC': {'required': ['abc'], 'outputs': ['YUE2_ABC']},
    'YuE2SongTokens': {'required': ['run', 'engine', 'prompt', 'maximum_song_length'],
                       'optional': ['plan', 'custom_abc'], 'outputs': ['YUE2_TOKENS']},
    'YuE2SynthesizeLatents': {'required': ['run', 'tokens', 'steps', 'method'],
                              'outputs': ['YUE2_LATENTS']},
    'YuE2DecodeAudio': {'required': ['run', 'latents'], 'outputs': ['AUDIO']},
    'YuE2SaveSong': {'required': ['run', 'tokens', 'audio'], 'outputs': ['AUDIO']},
    'YuE2AnalyzeMelody': {'required': ['audio', 'transcribe_lyrics', 'language'],
                          'outputs': ['YUE2_ABC']},
    'YuE2ReleaseEngine': {'required': [], 'outputs': []},
}


def get(path, timeout=20):
    with urllib.request.urlopen(f'http://127.0.0.1:{PORT}{path}', timeout=timeout) as response:
        return response.read()


def main():
    log = (SANDBOX / 'comfyui-server.log').open('w')
    process = subprocess.Popen(
        [sys.executable, '-u', 'main.py', '--listen', '127.0.0.1', '--port', str(PORT),
         '--output-directory', str(OUTPUTS), '--disable-auto-launch', '--preview-method', 'none',
         '--cpu'],  # sandbox has no GPU; the Kaggle cell launches without --cpu
        cwd=str(COMFY_DIR), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(90):
            if process.poll() is not None:
                raise RuntimeError('server exited:\n' + log.name and open(log.name).read()[-3000:])
            try:
                get('/system_stats', timeout=2)
                break
            except Exception:
                time.sleep(1)
        else:
            raise TimeoutError('server did not start')
        print('server up; pid', process.pid)

        # 1. object_info registration
        info = json.loads(get('/object_info'))
        missing = [name for name in EXPECTED_NODES if name not in info]
        assert not missing, f'nodes missing from object_info: {missing}'
        for name, spec in EXPECTED_NODES.items():
            entry = info[name]
            required = list(entry['input'].get('required', {}))
            optional = list(entry['input'].get('optional', {}))
            for want in spec['required']:
                assert want in required, f'{name}: required input {want} missing ({required})'
            for want in spec.get('optional', []):
                assert want in optional, f'{name}: optional input {want} missing'
            got_outputs = [o[0] if isinstance(o, (list, tuple)) else o
                           for o in entry['output']]
            assert got_outputs == spec['outputs'], f'{name}: outputs {got_outputs} != {spec["outputs"]}'
        print('object_info: all', len(EXPECTED_NODES), 'KaggleYuE2 nodes registered with expected inputs/outputs')

        # 2. web assets served
        for asset, marker in (('open_workflow.js', 'KaggleYuE2.OpenWorkflow'),
                              ('yue2-song.json', 'YuE2SaveSong'),
                              ('yue2-cover.json', 'YuE2AnalyzeMelody')):
            body = get(f'/extensions/KaggleYuE2/{asset}').decode()
            assert marker in body, f'{asset} does not contain {marker}'
        print('web assets served: open_workflow.js + both canvases')

        # 3. fake input audio so the cover canvas can validate
        import numpy as np
        import soundfile as sf
        input_dir = COMFY_DIR / 'input'
        input_dir.mkdir(exist_ok=True)
        sf.write(str(input_dir / 'sandbox-song.wav'),
                 np.zeros((48000, 2), dtype=np.float32), 48000, subtype='FLOAT')

        # 4. validate both canvases through ComfyUI's own prompt validator
        for name in ('song', 'cover'):
            canvas = json.loads(get(f'/extensions/KaggleYuE2/yue2-{name}.json'))
            prompt = canvas_to_api(canvas, info, fake_audio='sandbox-song.wav')
            request = urllib.request.Request(
                f'http://127.0.0.1:{PORT}/prompt',
                data=json.dumps({'prompt': prompt, 'client_id': 'sandbox-validate'}).encode(),
                headers={'Content-Type': 'application/json'}, method='POST')
            try:
                body = json.loads(urllib.request.urlopen(request, timeout=30).read().decode())
                assert body.get('prompt_id'), body
                print(f'canvas "{name}": ComfyUI validator ACCEPTED the graph (prompt_id={body["prompt_id"][:8]})')
                urllib.request.urlopen(urllib.request.Request(
                    f'http://127.0.0.1:{PORT}/interrupt', data=b'', method='POST'), timeout=10)
            except urllib.error.HTTPError as error:
                detail = error.read().decode()
                raise AssertionError(f'canvas "{name}" REJECTED by ComfyUI validator: {detail[:2000]}')
        print('ALL INTEGRATION CHECKS PASSED')
    finally:
        process.terminate()
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            process.kill()
        log.close()


def canvas_to_api(canvas, info, fake_audio=None):
    """Convert UI workflow JSON to API prompt using object_info input order."""
    links = {link[0]: (link[1], link[2]) for link in canvas['links']}
    prompt = {}
    for node in canvas['nodes']:
        definition = info[node['type']]
        schema = {'required': definition['input'].get('required', {}),
                  'optional': definition['input'].get('optional', {})}
        connected = {i['name']: i['link'] for i in node.get('inputs', []) if i.get('link') is not None}
        widgets = list(node.get('widgets_values', []))
        inputs = {}
        for group in ('required', 'optional'):
            for input_name, input_spec in schema[group].items():
                if input_name in ('PROMPT', 'UNIQUE_ID', 'EXTRA_PNGINFO', 'OUTPUT_FLOW'):
                    continue
                kind = input_spec[0]
                if isinstance(kind, list):  # combo
                    if input_name in connected:
                        origin, slot = links[connected[input_name]]
                        inputs[input_name] = [str(origin), slot]
                    else:
                        value = widgets.pop(0) if widgets else (kind[0] if kind else None)
                        if fake_audio and value == '':
                            value = fake_audio
                        inputs[input_name] = value
                elif isinstance(kind, str) and kind.upper() in {
                        'AUDIO', 'IMAGE', 'LATENT', 'MODEL', 'CLIP', 'VAE', 'CONDITIONING',
                        'YUE2_RUN', 'YUE2_ENGINE', 'YUE2_PROMPT', 'YUE2_PLAN', 'YUE2_ABC',
                        'YUE2_TOKENS', 'YUE2_LATENTS', 'GUIDER', 'SAMPLER', 'SIGMAS', 'NOISE'}:
                    if input_name in connected:
                        origin, slot = links[connected[input_name]]
                        inputs[input_name] = [str(origin), slot]
                    elif group == 'required':
                        raise AssertionError(
                            f'{node["type"]}: required link input {input_name} is not wired in the canvas')
                    # unconnected optional link inputs are omitted
                else:
                    if input_name in connected:
                        origin, slot = links[connected[input_name]]
                        inputs[input_name] = [str(origin), slot]
                    else:
                        inputs[input_name] = widgets.pop(0) if widgets else input_spec[1].get('default')
        prompt[str(node['id'])] = {'class_type': node['type'], 'inputs': inputs}
    return prompt


if __name__ == '__main__':
    main()
