"""Verify revision 16 mechanics end to end on this machine.

A. The pinned ComfyUI checkout is saved as a tar snapshot (exactly what the
   builder does, including its shallow git metadata), then restored into a
   fresh target from the snapshot alone with the origin deliberately
   unreachable - the Kaggle offline-session path.
B. add_comfyui_assets() resolves a requirements set, keeps the wheel already
   in the wheelhouse, downloads only the missing one, and stores a snapshot
   whose listing carries the pinned main.py.
C. A fresh venv resolves the requirements fully offline from that wheelhouse -
   what a Kaggle session does with the rebuilt dataset.
"""
import json
import subprocess
import sys
import tempfile
import unittest.mock
from pathlib import Path

SUPPORT = Path('/home/z/my-project/gh/Music')
SANDY_COMFY = Path('/home/z/my-project/comfy_sandbox/ComfyUI')
COMFY_COMMIT = '423cbd20511becb1f16122ab518e92e58bfa03d9'
assert subprocess.check_output(['git', '-C', str(SANDY_COMFY), 'rev-parse', 'HEAD'],
                               text=True).strip() == COMFY_COMMIT, 'sandbox checkout moved'

sys.path.insert(0, str(SUPPORT))
from native_yue2 import assets, setup  # noqa: E402


def head(path):
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()


def step_a_snapshot_restores_offline(base: Path):
    snapshot = base / 'comfyui-snapshot.tar.gz'
    subprocess.run(['tar', '-C', str(SANDY_COMFY), '-czf', str(snapshot), '.'],
                   check=True, capture_output=True)
    listing = subprocess.run(['tar', '-tzf', str(snapshot), './main.py'],
                             capture_output=True, text=True)
    assert listing.returncode == 0, 'snapshot lacks the ComfyUI main.py'
    target = base / 'restored-comfyui'
    setup._pinned_checkout('file:///nonexistent/comfyui.git', COMFY_COMMIT, target,
                           snapshot=snapshot)
    assert head(target) == COMFY_COMMIT
    assert (target / 'main.py').is_file()
    print('A. PASS  offline snapshot restore of the real pinned ComfyUI checkout')


def step_b_delta_wheels(base: Path):
    origin = base / 'mini-origin'
    origin.mkdir()
    (origin / 'main.py').write_text('# mini comfy\n')
    (origin / 'requirements.txt').write_text('six==1.16.0\npackaging==24.0\n')
    subprocess.run(['git', '-C', str(origin), 'init', '-q'], check=True)
    subprocess.run(['git', '-C', str(origin), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(origin), '-c', 'user.email=t@t', '-c', 'user.name=t',
                    'commit', '-qm', 'pin'], check=True)
    commit = head(origin)
    destination = base / 'assets'
    wheelhouse = destination / 'wheelhouse'
    wheelhouse.mkdir(parents=True)
    subprocess.run([sys.executable, '-m', 'pip', 'download', '--no-deps', '--only-binary=:all:',
                    '-d', str(wheelhouse), 'six==1.16.0'], check=True, capture_output=True)
    saved_six = wheelhouse / 'six-1.16.0-py2.py3-none-any.whl'
    assert saved_six.is_file()
    six_inode = saved_six.stat().st_ino
    constraint = base / 'kaggle-constraints.txt'
    constraint.write_text('')  # No binary pins for this mini stack.
    (base / 'comfyui-src').mkdir()
    subprocess.run(['git', '-C', str(origin), 'checkout', '-q', '--detach', commit], check=True)
    # Point the checkout at the mini origin and the commit at its HEAD.
    with unittest.mock.patch.object(setup, 'COMFYUI_REPO', str(origin)), \
         unittest.mock.patch.object(setup, 'COMFYUI_COMMIT', commit):
        assets.add_comfyui_assets(destination, base, env=None)
    assert (destination / 'comfyui-snapshot.tar.gz').is_file()
    listing = subprocess.run(['tar', '-tzf', str(destination / 'comfyui-snapshot.tar.gz'),
                              './main.py'], capture_output=True, text=True)
    assert listing.returncode == 0
    assert saved_six.stat().st_ino == six_inode, 'existing wheel was re-fetched'
    packaging = list(wheelhouse.glob('packaging-24.0-*.whl'))
    assert packaging, 'missing wheel was not downloaded'
    print(f'B. PASS  kept saved wheel, fetched only the gap ({packaging[0].name}), snapshot verified')
    return destination


def step_c_offline_resolution(base: Path, destination: Path):
    check = base / 'offline-check'
    subprocess.run([sys.executable, '-m', 'venv', '--without-pip', str(check)], check=True)
    result = subprocess.run(
        [sys.executable, '-m', 'pip', '--python', str(check / 'bin' / 'python'), 'install',
         '--dry-run', '--no-index', '--find-links', str(destination / 'wheelhouse'),
         '-r', str(base / 'mini-origin' / 'requirements.txt')], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    assert 'Would install' in result.stdout and 'packaging' in result.stdout
    print('C. PASS  fresh environment resolves fully offline from the wheelhouse')


def main():
    with tempfile.TemporaryDirectory(prefix='rev16-verify-') as name:
        base = Path(name)
        step_a_snapshot_restores_offline(base)
        destination = step_b_delta_wheels(base)
        step_c_offline_resolution(base, destination)
    print('ALL REV16 MECHANICS VERIFIED')


if __name__ == '__main__':
    main()
