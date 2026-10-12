import argparse
import json
from pathlib import Path
from .runner import Runner, Task


def main():
    parser = argparse.ArgumentParser(description='Bounded resumable GOLDEN MOTION harness')
    parser.add_argument('action', choices=['run', 'status'], nargs='?', default='status')
    parser.add_argument('--budget', type=float, default=1800, help='Overall wall time seconds')
    parser.add_argument('--max-tasks', type=int, default=20)
    parser.add_argument('--task', action='append', help='Select a task and its prerequisites')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root/'harness/tasks.json').read_text())
    tasks = [Task(**t) for t in config['tasks']]
    if args.task:
        by_id = {t.id:t for t in tasks}
        selected = set()
        def add(id):
            if id not in by_id:
                parser.error('Unknown task '+id)
            if id not in selected:
                selected.add(id)
                for d in by_id[id].depends:
                    add(d)
        for id in args.task:
            add(id)
        tasks = [t for t in tasks if t.id in selected]
    r = Runner(root, tasks)
    if args.action == 'run':
        summary = r.run(max_tasks=args.max_tasks, budget_s=args.budget)
        print(json.dumps(summary, indent=2))
        return 1 if any(r.state['tasks'][t.id]['status'] == 'failed' for t in tasks) else 0
    print(json.dumps({id:{k:v for k,v in entry.items() if k != 'evidence'}
                      for id,entry in r.state['tasks'].items()}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
