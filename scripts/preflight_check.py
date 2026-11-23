"""Run the real Music Studio preflight against every pinned remote.

Verifies each URL in catalog.json + sources.json is reachable and reports the
server-side byte length vs the pinned size. Usage: python preflight_check.py <repo_root>
"""
import json
import sys
from pathlib import Path

REPO = Path(sys.argv[1])
sys.path.insert(0, str(REPO))
from music_studio import preflight  # noqa: E402

catalog = json.loads((REPO / 'music_studio/catalog.json').read_text())
sources = json.loads((REPO / 'music_studio/sources.json').read_text())
records = preflight.remote_records(catalog, sources)
print(f'{len(records)} pinned remotes')
results = []
for record in records:
    state, size = preflight.probe(record['source'], timeout=30)
    status = {True: 'OK size match', False: 'SIZE MISMATCH'}[state == 'ok' and size == record['bytes']] \
        if state == 'ok' else f'{state} ({size})'
    results.append((record['kind'], record['name'], record['bytes'], size, status))
    print(f'  {record["kind"]:9} {record["name"][:52]:52} pinned={record["bytes"]:>12} server={size} -> {status}')

bad = [r for r in results if 'OK' not in r[4]]
print('\nFAILING:', len(bad))
for r in bad:
    print('   ', r)
