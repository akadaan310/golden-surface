"""Install locked workspace dependencies locally. No credentials or hosting."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def run(argv, timeout=900):
    print('Bootstrap:', ' '.join(argv), flush=True)
    subprocess.run(argv, cwd=ROOT, timeout=timeout, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skip-android', action='store_true')
    parser.add_argument('--skip-numerics', action='store_true')
    parser.add_argument('--skip-browser', action='store_true')
    args = parser.parse_args()
    run(['npm','ci','--no-audit','--no-fund'])
    req = ROOT/'science/requirements.txt'
    if req.exists():
        if not (ROOT/'.venv/bin/python').exists():
            run([sys.executable,'-m','venv',str(ROOT/'.venv')])
        run([str(ROOT/'.venv/bin/python'),'-m','pip','install','-r',str(req),'-r',str(ROOT/'requirements-harness.txt')], 600)
    if not args.skip_numerics:
        numerical_setup = ROOT/'science/bootstrap-tools.sh'
        if numerical_setup.exists():
            run(['bash',str(numerical_setup)],900)
        else:
            print('Numerical tools: see science/README.md for optional Julia/Octave setup.')
    if not args.skip_android:
        native_setup = ROOT/'apps/android/scripts/bootstrap.sh'
        if native_setup.exists():
            run(['bash',str(native_setup)],1200)
        else:
            print('Android tools: see apps/android/README.md for SDK setup and build.')
    if not args.skip_browser:
        run(['npx','playwright','install','chromium'],600)
    run([sys.executable, 'scripts/environment.py'])
    print('Bootstrap finished. Run: npm run verify', flush=True)


if __name__ == '__main__':
    main()
