"""Emulate the Music Studio Dataset publish() flow against the REAL kaggle 2.0.2.

Only the HTTP transport (requests.Session.send) and the 25 GB model downloads
(dataset.transfer) are replaced; every SDK method the builder touches is the
real PyPI wheel. Run with the kaggle-venv python:
  /home/z/my-project/gh/_pins/kaggle-venv/bin/python -I verify_kaggle_sdk.py <repo_root>
"""
import hashlib
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

REPO = Path(sys.argv[1])
sys.path.insert(0, str(REPO))

os.environ['KAGGLE_USERNAME'] = 'test-owner'
os.environ['KAGGLE_KEY'] = '0' * 32  # fake; no network leaves this process
os.environ.pop('KAGGLE_API_TOKEN', None)

import requests  # noqa: E402

CALLS = []


class FakeResponse:
    def __init__(self, status_code, body, headers=None):
        self.status_code = status_code
        self.headers = {'Content-Type': 'application/json'}
        if headers:
            self.headers.update(headers)
        self._body = body
        self.request = types.SimpleNamespace(method='POST', url='fake')

    def json(self):
        return self._body

    @property
    def text(self):
        if isinstance(self._body, (str, bytes)):
            return self._body.decode() if isinstance(self._body, bytes) else self._body
        return json.dumps(self._body)

    @property
    def content(self):
        return self.text.encode()

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests as r
            raise r.exceptions.HTTPError(f'{self.status_code} error', response=self)


def fake_send(self, request, **kwargs):
    url = request.url
    method = request.method
    CALLS.append(f'{method} {url}')
    if 'GetDatasetStatus' in url or 'datasets/status' in url:
        return FakeResponse(404, {'code': 404, 'message': 'Dataset not found'})
    if 'StartBlobUpload' in url:
        return FakeResponse(200, {'token': 'fake-blob-token', 'create_url': 'http://127.0.0.1:1/put',
                                  'createUrl': 'http://127.0.0.1:1/put', 'expires_in': 3600})
    if 'CreateDataset' in url:
        return FakeResponse(200, {'status': 'ok', 'error': '', 'url': 'https://www.kaggle.com/datasets/test-owner/fake'})
    if request.method == 'PUT':
        return FakeResponse(200, {})
    return FakeResponse(200, {})


def main():
    from music_studio import common, dataset

    def transfer(record, destination, reserve=0):
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'x' * record['bytes'])
        return destination

    runtime = dict(name='music-studio-runtime.bundle', bytes=7, sha256=hashlib.sha256(b'runtime').hexdigest(),
                   architecture='x86_64', cuda_architectures=[75], build_mode='cuda',
                   source_fingerprint=common.fingerprint(json.loads((common.HERE / 'sources.json').read_text())),
                   compatibility={'libc': ['glibc', '2.35'], 'cuda': '13.0.2'})
    assets = []
    for n, size in ((1, 2048), (2, 4096)):
        data = b'x' * size
        (REPO / '_kaggle_emu' / f'asset-{n}.bin').parent.mkdir(exist_ok=True)
        (REPO / '_kaggle_emu' / f'asset-{n}.bin').write_bytes(data)
        assets.append(dict(name=f'asset-{n}.bin', path=f'models/asset-{n}.bin', bytes=size,
                           sha256=hashlib.sha256(data).hexdigest(), role='test', license='test-only',
                           source='https://example.invalid/'))
    runtime_path = REPO / '_kaggle_emu' / 'music-studio-runtime.bundle'
    runtime_path.write_bytes(b'runtime')
    catalog = dict(schema=1, profile=common.PROFILE, assets=assets)
    manifest = dict(schema=1, profile=common.PROFILE, complete=True,
                    catalog_fingerprint=common.fingerprint(catalog), files=assets, runtime=runtime,
                    model_bytes=sum(r['bytes'] for r in assets))

    with patch.object(requests.Session, 'send', fake_send), \
            patch.object(common, 'catalog', return_value=catalog), \
            patch.object(dataset, 'transfer', side_effect=transfer):
        api = dataset.authenticated_api()  # REAL authenticate() with legacy env creds
        owner = dataset.username(api)
        print('authenticated username:', owner, '| auth method:', api.config_values.get('auth_method', '?'))
        url = dataset.publish(manifest, runtime_path, output_root=REPO / '_kaggle_emu' / 'out',
                              input_root=REPO / '_kaggle_emu', owner=owner, api=api)
    print('publish returned:', url)
    print('receipt:', json.loads((REPO / '_kaggle_emu' / 'out' / 'dataset-upload.json').read_text()))
    puts = [c for c in CALLS if c.startswith('PUT')]
    statuses = [c for c in CALLS if 'GetDatasetStatus' in c]
    creates = [c for c in CALLS if 'CreateDataset' in c and 'Status' not in c]
    print(f'transport calls: {len(CALLS)} total, {len(puts)} file PUTs, {len(statuses)} status, {len(creates)} create')
    assert owner == 'test-owner', owner
    assert len(puts) == 5, puts  # runtime + 2 assets + manifest + notices
    assert len(statuses) == 1 and len(creates) == 1, CALLS
    handle, _ = dataset.identity(owner, manifest)
    assert url.endswith(handle), (url, handle)
    print('REAL SDK 2.0.2 EMULATION: ALL CHECKS PASSED')


if __name__ == '__main__':
    main()
