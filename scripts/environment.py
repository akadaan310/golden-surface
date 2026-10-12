"""Non-secret capability inventory. Never dumps environment or credential files."""
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]


def command_version(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return {'available': r.returncode == 0,
                'version': (r.stdout+r.stderr).strip()[:1500], 'exitCode': r.returncode}
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {'available': False, 'reason': str(exc)}


def discover():
    tools = {}
    for name, argv in {'node':['node','--version'], 'npm':['npm','--version'],
                       'python':[sys.executable,'--version'], 'java':['java','-version'],
                       'julia':['julia','--version'], 'octave':['octave','--version'],
                       'adb':['adb','devices','-l']}.items():
        tools[name] = command_version(argv)
    for name, patterns in {'julia':['science/.tools/julia*/bin/julia', '.tools/julia*/bin/julia', '.tools/julia/bin/julia'],
                           'octave':['science/.tools/octave/bin/octave-cli', 'science/.tools/octave/bin/octave', '.tools/octave*/usr/bin/octave', '.tools/octave/bin/octave'],
                           'adb':['.tools/android/platform-tools/adb']}.items():
        if not tools[name]['available']:
            for pattern in patterns:
                candidates = list(ROOT.glob(pattern))
                if candidates:
                    arg = ['devices','-l'] if name == 'adb' else ['--version']
                    tools[name] = command_version([str(candidates[0]), *arg])
                    tools[name]['path'] = str(candidates[0].relative_to(ROOT))
                    break
    packages = {}
    for name in ['numpy','scipy','matplotlib','psutil']:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    free = shutil.disk_usage(ROOT)
    result = {'timestamp': datetime.now(timezone.utc).isoformat(),
              'system': platform.platform(), 'architecture': platform.machine(),
              'cpuCount': os.cpu_count(), 'diskFreeBytes': free.free,
              'tools': tools, 'pythonPackages': packages,
              'hardwareValidation': 'pending actual Galaxy A16 connection',
              'credentialsInspected': False}
    (ROOT/'artifacts').mkdir(exist_ok=True)
    (ROOT/'artifacts/environment.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(discover(), indent=2))
