"""Standalone reproduction of the two failing ToolkitEnvTests (outside unittest).

Replicates the test bodies exactly so the failure can be bisected step by step.
Run with the repo root as argv[1].
"""
import io
import json
import os
import sys
import tarfile
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

root = Path(sys.argv[1])
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / 'tests' / 'music_studio'))

from music_studio import build_runtime  # noqa: E402
from music_studio.common import fingerprint  # noqa: E402


def repro_refetch():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        cuda = work / 'cuda'
        (cuda / 'bin').mkdir(parents=True)
        for name in ('nvcc', 'ptxas', 'cudafe++'):
            (cuda / 'bin' / name).write_text('fixture')
        sources = dict(runtime_assets=[
            dict(id='cuda_nvcc', name='nvcc.tar.xz', source='https://example.invalid/nvcc', sha256='0' * 64, bytes=1),
            dict(id='cuda_cudart', name='cudart.tar.xz', source='https://example.invalid/cudart', sha256='2' * 64, bytes=1),
        ])
        selected = sources['runtime_assets']
        for record in selected:
            (cuda / ('.asset-' + record['id'])).write_text(record['sha256'])
        (cuda / '.complete').write_text(fingerprint(selected))
        archive = work / 'cudart.tar.xz'
        with tarfile.open(archive, 'w:xz') as tar:
            for name in ('lib/libcudart_static.a', 'lib/libcudadevrt.a'):
                data = b'cudart fixture'
                member = tarfile.TarInfo('cuda/' + name)
                member.mode, member.size = 0o644, len(data)
                tar.addfile(member, io.BytesIO(data))
        env = dict(os.environ)
        with patch.object(build_runtime, 'transfer', return_value=archive) as transfer, \
                patch.object(build_runtime, 'validate_cuda_compiler'):
            build_runtime.toolkit(work, sources, env)
        print('refetch OK; transfer calls:', [c.args[0]['id'] for c in transfer.call_args_list])


def repro_complete():
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        cuda = work / 'cuda'
        cuda.mkdir()
        sources = dict(runtime_assets=[
            dict(id='cuda_nvcc', name='nvcc.tar.xz', source='https://example.invalid/nvcc', sha256='0' * 64, bytes=1),
            dict(id='cuda_cudart', name='cudart.tar.xz', source='https://example.invalid/cudart', sha256='2' * 64, bytes=1),
            dict(id='libcublas', name='cublas.tar.xz', source='https://example.invalid/cublas', sha256='1' * 64, bytes=1),
        ])
        selected = [r for r in sources['runtime_assets'] if r['id'].startswith('cuda_') or r['id'] in ('libcublas', 'libnvvm')]
        (cuda / 'bin').mkdir()
        for name in ('nvcc', 'ptxas', 'cudafe++'):
            (cuda / 'bin' / name).write_text('fixture')
        (cuda / 'lib').mkdir()
        for name in ('libcudart_static.a', 'libcudadevrt.a', 'libcudart.so.13'):
            (cuda / 'lib' / name).write_text('fixture')
        for record in selected:
            (cuda / ('.asset-' + record['id'])).write_text(record['sha256'])
        (cuda / '.complete').write_text(fingerprint(selected))
        env = dict(os.environ)
        with patch.object(build_runtime, 'transfer') as transfer, patch.object(build_runtime, 'validate_cuda_compiler'):
            build_runtime.toolkit(work, sources, env)
        transfer.assert_not_called()
        print('complete OK')


if __name__ == '__main__':
    which = sys.argv[2] if len(sys.argv) > 2 else 'both'
    if which in ('both', 'refetch'):
        repro_refetch()
    if which in ('both', 'complete'):
        repro_complete()
    print('done')
