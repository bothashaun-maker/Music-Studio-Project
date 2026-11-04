"""Prove the real Kaggle crash and the wheelhouse-first fix, end to end.

Scenario = the 2026-11-04 Kaggle log: assets mode (PIP_NO_INDEX=1), a saved
wheelhouse that predates ComfyUI v0.43.2, and `pip install -r
ComfyUI/requirements.txt` needing comfyui-frontend-package==1.57.4.

  1. Old behaviour, for real: hard offline wall -> the exact user error.
  2. New kaggle_yue2.runtime.pip_install: same env -> PyPI fills only the gap.
  3. Complete wheelhouse: helper stays fully offline, no fallback at all.
"""
import contextlib
import importlib.metadata
import io
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path('/home/z/my-project/gh/Music')
sys.path.insert(0, str(ROOT))

PIN = 'comfyui-frontend-package==1.57.4'   # exact pin from ComfyUI v0.43.2
NAME = 'comfyui-frontend-package'
RESULTS = []


def check(label, ok):
    RESULTS.append((label, bool(ok)))
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")


def run(cmd, env=None):
    return subprocess.run([str(x) for x in cmd], env=env, text=True, capture_output=True)


def make_venv(base):
    target = base / f'venv{len(list(base.glob("venv*"))) + 1}'
    venv.create(target, with_pip=True)
    return target / 'bin' / 'python'


def version_in(venv_python):
    out = run([venv_python, '-c',
               f'import importlib.metadata as m; print(m.version("{NAME}"))'])
    return out.stdout.strip() if out.returncode == 0 else None


def main():
    from kaggle_yue2.runtime import pip_install  # the shipped fix

    base = Path(tempfile.mkdtemp(prefix='yue2-pip-proof-'))
    try:
        # A real wheelhouse with a real wheel — but NOT the wheel ComfyUI pins.
        wheelhouse = base / 'wheelhouse'
        wheelhouse.mkdir()
        got = run([sys.executable, '-m', 'pip', 'download', '--no-deps', '-q',
                   '-d', str(wheelhouse), 'six==1.17.0'])
        assert got.returncode == 0, got.stderr
        requirements = base / 'requirements.txt'
        requirements.write_text(PIN + '\n')

        # 1 · Old behaviour, for real: the user's exact crash, byte for byte.
        print('[1] offline wall with the user\'s env (old behaviour):')
        offline_env = dict(os.environ, PIP_NO_INDEX='1',
                           PIP_FIND_LINKS=str(wheelhouse),
                           PIP_DISABLE_PIP_VERSION_CHECK='1')
        old = run([make_venv(base), '-m', 'pip', 'install', '--no-cache-dir',
                   '-r', requirements], env=offline_env)
        combined = old.stdout + old.stderr
        check('old path fails exactly like the Kaggle log',
              old.returncode != 0 and
              'No matching distribution found for ' + PIN in combined)

        # 2 · The shipped helper: same env, same requirements -> self-heals.
        print('[2] pip_install with the same env (the fix):')
        fresh = make_venv(base)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pip_install(fresh, ['-r', requirements], env=offline_env,
                        wheelhouse=wheelhouse, purpose='the pinned ComfyUI packages')
        log = buf.getvalue()
        check('fallback reported itself and fetched only the gap',
              'fetching only the missing wheels' in log and
              'the pinned ComfyUI packages' in log)
        check('wheel installed at the exact pinned version',
              version_in(fresh) == '1.57.4')

        # 3 · A complete wheelhouse must stay 100% offline: no fallback at all.
        print('[3] complete wheelhouse (no fallback allowed):')
        wheelhouse2 = base / 'wheelhouse2'
        wheelhouse2.mkdir()
        got = run([sys.executable, '-m', 'pip', 'download', '--no-deps', '-q',
                   '-d', str(wheelhouse2), PIN])
        assert got.returncode == 0, got.stderr
        fresh2 = make_venv(base)
        buf2 = io.StringIO()
        with contextlib.redirect_stdout(buf2):
            pip_install(fresh2, ['-r', requirements], env=dict(os.environ),
                        wheelhouse=wheelhouse2, purpose='the pinned ComfyUI packages')
        check('offline attempt succeeded — no PyPI fallback printed',
              'fetching only the missing wheels' not in buf2.getvalue())
        check('wheel came from the saved wheelhouse', version_in(fresh2) == '1.57.4')
    finally:
        shutil.rmtree(base, ignore_errors=True)

    failed = [label for label, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if failed:
        print('FAILED:', *failed, sep='\n  - ')
        return 1
    print('ALL PASS: the Kaggle crash is reproduced and the fix self-heals it.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
