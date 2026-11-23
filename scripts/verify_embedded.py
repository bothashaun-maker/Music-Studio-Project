"""Check that the embedded sources in the Music Studio notebooks equal the repo sources."""
import hashlib, json, pathlib, sys
BASE = pathlib.Path('/home/z/my-project/gh/Music-fix')
D = BASE / '_inspect' / 'decoded'

def sha(b): return hashlib.sha256(b).hexdigest()

for label, repo_dir in (('musicstudio', BASE / 'music_studio'), ('dataset', BASE / 'music_studio')):
    print(f'--- {label}: embedded vs repo {repo_dir.relative_to(BASE)}')
    dec = D / label
    for f in sorted(p for p in dec.rglob('*') if p.is_file()):
        rel = f.relative_to(dec)          # decoded keys were written with '\' -> '/'
        repo = repo_dir / rel.name        # the package sources are flat in music_studio/
        if not repo.exists():
            print('  NOT IN REPO :', rel); continue
        same = sha(f.read_bytes()) == sha(repo.read_bytes())
        print('  ', 'same   ' if same else 'DIFFERS', rel, f.stat().st_size)
    for repo in sorted(p for p in repo_dir.iterdir() if p.is_file()):
        if not (dec / repo.name).exists():
            print('   EMBED MISSING for repo file', repo.name)
