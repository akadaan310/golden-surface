"""Execute graph checks and preserve failures; hardware remains separately pending."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from harness.runner import Runner, Task


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--budget', type=float, default=3600)
    parser.add_argument('--quick', action='store_true', help='Skip numerical parity, browser and native build')
    parser.add_argument('--force', action='store_true', help='Rerun previously successful checks')
    args = parser.parse_args()
    tasks = [Task(**t) for t in json.loads((ROOT/'harness/tasks.json').read_text())['tasks']]
    if args.quick:
        tasks = [t for t in tasks if t.id not in ['numeric-parity', 'rf-parity', 'android-build', 'browser-e2e']]
    runner = Runner(ROOT,tasks)
    if args.force:
        for t in tasks:
            runner.state['tasks'].pop(t.id,None)
    summary = runner.run(max_tasks=30, budget_s=args.budget)
    print(json.dumps(summary,indent=2))
    failed = [t.id for t in tasks if runner.state['tasks'][t.id]['status'] == 'failed']
    unfinished = [t.id for t in tasks if not t.requires_hardware and
                  runner.state['tasks'][t.id]['status'] in ['pending','blocked']]
    if failed or unfinished:
        print('Failed:',failed,'Unfinished:',unfinished)
        return 1
    print('Selected engineering/synthetic checks passed. Physical validation is pending.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
