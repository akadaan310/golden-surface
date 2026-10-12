"""Portable source/experiment package with SHA256; excludes dependencies and media."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    archive = ROOT/'artifacts/golden-motion-source.tar.gz'
    excluded = {'node_modules','.git','.next','out','.venv','.gradle','build',
                '.tools','__pycache__','.pytest_cache','test-results','playwright-report'}
    count = 0
    with tarfile.open(archive,'w:gz') as tar:
        for path in sorted(ROOT.rglob('*')):
            if not path.is_file() or any(part in excluded for part in path.relative_to(ROOT).parts):
                continue
            if path == archive or path.suffix == '.apk' or path.name.startswith('.env'):
                continue
            if 'recordings' in path.parts:
                continue
            tar.add(path, arcname=Path('golden-motion')/path.relative_to(ROOT))
            count += 1
    result = {'archive':str(archive.relative_to(ROOT)), 'files':count,
              'bytes':archive.stat().st_size, 'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()}
    (ROOT/'artifacts/package-manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    main()
