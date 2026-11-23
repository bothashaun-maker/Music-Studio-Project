"""Run the Music Studio tests one by one and report which test breaks fd 0/1/2.

Baseline check for the documented command:
    python -m unittest discover -s tests/music_studio -v
Usage: python fd_bisect.py <repo_root>
"""
import os
import sys
import unittest

root = sys.argv[1]
sys.path.insert(0, root)
sys.path.insert(0, os.path.join(root, 'tests', 'music_studio'))


def healthy(fd):
    try:
        os.fstat(fd)
        return True
    except OSError:
        return False


log = open('/home/z/my-project/scripts/_fd_bisect.log', 'w')
before = {fd: healthy(fd) for fd in (0, 1, 2)}
print('start fds healthy:', before, file=log, flush=True)
loader = unittest.TestLoader()
import test_dataset_flow, test_packaging  # noqa: E402
suite = unittest.TestSuite()
for module in (test_dataset_flow, test_packaging):
    for name in sorted(dir(module)):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj.__module__ == module.__name__:
            suite.addTests(loader.loadTestsFromTestCase(obj))

for index, test in enumerate(suite):
    result = unittest.TestResult()
    test.run(result)
    after = {fd: healthy(fd) for fd in (0, 1, 2)}
    changed = after != before
    before = after
    line = f'{index:2} {test.id()[:90]:90} ok={result.wasSuccessful()} fds={after}' + ('   <== CHANGED' if changed else '')
    os.write(9 if False else log.fileno(), (line + '\n').encode())
    log.flush()
log.close()
