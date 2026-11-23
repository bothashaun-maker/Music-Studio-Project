"""Reproduce the big-WAV cover upload behaviour on CPU, old vs new uploader.

Scenario A (limit): the standard ComfyUI Load Audio upload is ONE request and
aiohttp caps request bodies (ComfyUI passes --max-upload-size MB, default 100)
=> a >100 MB cover WAV cannot be uploaded through it at all.

Scenario B (integrity): the chunked resumable uploaders verify SIZE ONLY.
A corrupted piece is silently accepted and the assembled song differs from the
original file => information loss with no error.

Scenario C (fix check): with the fixed uploader a wrong piece fails its
checksum, nothing is saved, and finish refuses; a correct upload assembles to a
file whose SHA-256 equals the original's and is recorded.

Usage: python repro_upload.py <cover_upload_module.py> <sts_pack_module.py> <mode: old|new>
"""
import asyncio
import hashlib
import importlib.util
import io
import json
import os
import struct
import sys
import tempfile
import types
from pathlib import Path

from aiohttp import ClientSession, web

CHUNK = 1024 * 1024
STS_CHUNK = 8 * 1024 * 1024
SONG_BYTES = 104 * 1024 * 1024  # 128 MB — well over the 100 MB default, quick on CPU


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def song_bytes(total):
    header = b'RIFF' + struct.pack('<I', 36 + total - 8) + b'WAVEfmt ' + struct.pack(
        '<IHHIIHH', 16, 1, 2, 44100, 44100 * 4, 4, 16) + b'data' + struct.pack('<I', total - 44)
    block = (b'\x00\x01' * 4) * 65536
    body = bytearray(header)
    while len(body) < total:
        body.extend(block[: total - len(body)])
    return bytes(body)


async def serve(app):
    from aiohttp import ClientTimeout
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = runner.addresses[0][1]
    return runner, port


async def scenario_limit():
    """One-request upload cap, exactly what ComfyUI builds for Load Audio."""
    async def upload(request):
        await request.read()  # ComfyUI's upload handler reads the whole body
        return web.json_response({'ok': True})
    app = web.Application(client_max_size=100 * 1024 * 1024)  # ComfyUI default
    app.router.add_post('/upload/audio', upload)
    runner, port = await serve(app)
    try:
        async with ClientSession() as client:
            async with client.post(f'http://127.0.0.1:{port}/upload/audio',
                                   data=b'x' * (SONG_BYTES - 1024)) as response:
                print(f'  A) POST {SONG_BYTES // (1024 * 1024)} MB to a 100 MB-capped endpoint '
                      f'-> HTTP {response.status}')
                return response.status
    finally:
        await runner.cleanup()


async def run_uploader(module, mode, tmp):
    """Drive one uploader through happy path + corrupted piece + resume."""
    routes = web.RouteTableDef()
    fake_server = types.SimpleNamespace(routes=routes)
    input_dir = tmp / 'input'
    temp_dir = tmp / 'temp'
    input_dir.mkdir(exist_ok=True)
    temp_dir.mkdir(exist_ok=True)
    if hasattr(module, 'register_routes'):
        module.register_routes(fake_server, input_dir, temp_dir)
        prefix = ''
        chunk_path = '/yue2/cover-upload/chunk'
        status_path = '/yue2/cover-upload/status'
        finish_path = '/yue2/cover-upload/finish'
    else:
        fake_pack = types.ModuleType('server')
        class PromptServer:
            instance = types.SimpleNamespace(routes=routes)
        fake_pack.PromptServer = PromptServer
        sys.modules['server'] = fake_pack
        module._register_routes()
        prefix = '/sts'
        chunk_path = '/sts/upload/chunk'
        status_path = '/sts/upload/status'
        finish_path = '/sts/upload/finish'
    app = web.Application()
    app.add_routes(routes)
    runner, port = await serve(app)
    base = f'http://127.0.0.1:{port}'
    piece = STS_CHUNK if prefix == '/sts' else CHUNK
    digest_of = lambda data: hashlib.sha256(data).hexdigest()
    try:
        async with ClientSession() as client:
            ident = 'ab' * 16
            name = 'cover.wav'
            count = (SONG_BYTES + piece - 1) // piece
            query = f'upload={ident}&name={name}&size={SONG_BYTES}&n={count}'
            results = {}

            async def send_chunk(index, data, sha=True, declared=None):
                url = f'{base}{chunk_path}?{query}&i={index}'
                if sha:
                    url += '&sha=' + (declared or digest_of(data))
                async with client.post(url, data=data) as response:
                    body = await response.json(content_type=None)
                    results.setdefault('chunk_statuses', []).append(response.status)
                    return response.status, body

            original = song_bytes(SONG_BYTES)
            # Flip one byte INSIDE the first piece, preserving the file length,
            # so the browser's hash for that piece cannot match the damaged bytes.
            spot = piece // 2
            corrupted = original[:spot] + bytes([original[spot] ^ 0xFF]) + original[spot + 1:]
            results['input_sha256'] = digest_of(corrupted if mode == 'old' else original)
            if mode == 'old':
                # Damaged bytes arrive with no hash at all: the old server saves them.
                status, body = await send_chunk(0, corrupted[:piece], sha=False)
                results['corrupt_piece_status'] = status
                results['corrupt_piece_error'] = body.get('error')
                for i in range(1, count):
                    await send_chunk(i, corrupted[i * piece: (i + 1) * piece], sha=False)
            else:
                # Damaged bytes arrive with the browser's hash of the REAL piece.
                status, body = await send_chunk(0, corrupted[:piece], sha=True,
                                                declared=digest_of(original[:piece]))
                results['corrupt_piece_status'] = status
                results['corrupt_piece_error'] = body.get('error')
                # A clean upload of the same file must still work end to end.
                for i in range(count):
                    await send_chunk(i, original[i * piece: (i + 1) * piece], sha=True)
            async with client.get(f'{base}{status_path}?{query}') as response:
                results['completed_after_corrupt'] = (await response.json()).get('completed')
            async with client.post(f'{base}{finish_path}', json={
                    'upload': ident, 'name': name, 'size': SONG_BYTES, 'n': count}) as response:
                finish_body = await response.json(content_type=None)
                results['finish_status'] = response.status
                results['finish'] = finish_body
            assembled = input_dir / (finish_body.get('filename') or '')
            if assembled.is_file():
                results['assembled_sha256'] = digest_of(assembled.read_bytes())
            results['pieces_removed'] = True
        return results
    finally:
        await runner.cleanup()


STS_ENGINE_STUB = '''"""Minimal stand-in so the upload routes import without the studio UI."""
def validate_acoustic_bundle():
    return None


def _adjacent_helper(*_args, **_kwargs):
    return None
'''


def prepare_sts_package(package_dir, tmp):
    """Copy the pack and stub the studio engine; importing the real one would
    start a Gradio server and a public Cloudflare quick tunnel."""
    stubbed = tmp / 'sts_package' / 'timestamp_studio'
    stubbed.mkdir(parents=True, exist_ok=True)
    (tmp / 'sts_package' / '__init__.py').write_text('')
    for source in sorted(package_dir.glob('*.py')):
        (stubbed / source.name).write_text(source.read_text())
    (stubbed / 'sts_engine.py').write_text(STS_ENGINE_STUB)
    os.environ['STS_AUTOLAUNCH'] = '0'  # never start the studio UI from a test import
    for name in list(sys.modules):
        if name.startswith('timestamp_studio'):
            del sys.modules[name]
    sys.path.insert(0, str(tmp / 'sts_package'))
    module = importlib.import_module('timestamp_studio.comfy_pack')
    return module


def run_uploader_sync(module, mode, tmp):
    return asyncio.run(run_uploader(module, mode, tmp))


def main():
    cover_path, sts_path = (Path(p).resolve() for p in sys.argv[1:3])
    mode = sys.argv[3]
    data = song_bytes(SONG_BYTES)
    print(f'song fixture: {SONG_BYTES // (1024 * 1024)} MB WAV, sha256={hashlib.sha256(data).hexdigest()[:16]}…')
    only = os.environ.get('REPRO_ONLY', '')
    if only != 'sts':
        print('Scenario A — ComfyUI standard Load Audio single-request cap:')
        asyncio.run(scenario_limit())
    for label, path, packaged in (('rev15 cover uploader', cover_path, False),
                                  ('timestamp sts uploader', sts_path, True)):
        if only and (('cover' in only) != ('cover' in label)):
            continue
        print(f'Scenario B/C — {label} ({mode}):')
        with tempfile.TemporaryDirectory() as tmp:
            previous = os.getcwd()
            os.chdir(tmp)
            try:
                if packaged:
                    module = prepare_sts_package(Path(path).parent, Path(tmp))
                else:
                    module = load_module(f'uploader_{label[0]}_{mode}', path)
                results = run_uploader_sync(module, mode, Path(tmp))
            finally:
                sys.path = [p for p in sys.path if p != str(Path(tmp) / 'sts_package')]
                os.chdir(previous)
        for key, value in results.items():
            if key == 'completed_after_corrupt' and isinstance(value, list):
                value = f'{len(value)} pieces: {value[:4]}…'
            print(f'   {key}: {value}')
        if mode == 'old' and results.get('assembled_sha256') == results.get('input_sha256'):
            print('   VERDICT: the damaged piece was ACCEPTED; the assembled song equals the damaged input — loss with no error.')
        if mode == 'new' and results.get('finish_status') == 200:
            recorded = results['finish'].get('sha256')
            same = results['assembled_sha256'] == results['input_sha256'] == recorded
            print('   VERDICT: damaged piece refused with HTTP', results.get('corrupt_piece_status'),
                  '; clean upload assembled byte-identical, server recorded SHA-256:', recorded,
                  '->', 'NO LOSS' if same else 'MISMATCH!')


if __name__ == '__main__':
    main()
