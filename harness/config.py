"""Resolve interpreter and valid induced task graphs for all CLI entry points."""
import json
from pathlib import Path
import sys
from .model import Task


def load_tasks(root: Path):
    root=Path(root)
    environment_python=root/'.venv/bin/python'
    interpreter=str(environment_python) if environment_python.is_file() else sys.executable
    rows=json.loads((root/'harness/tasks.json').read_text())['tasks']
    result=[]
    for row in rows:
        row={**row,'command':list(row['command'])}
        if row['command'][0] in ['python','python3']:
            row['command'][0]=interpreter
        result.append(Task(**row))
    return result


def exclude_tasks(tasks, excluded):
    excluded=set(excluded)
    changed=True
    while changed:
        changed=False
        for task in tasks:
            if task.id not in excluded and any(dep in excluded for dep in task.depends):
                excluded.add(task.id);changed=True
    return [task for task in tasks if task.id not in excluded]
