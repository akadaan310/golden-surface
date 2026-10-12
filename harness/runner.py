"""A resumable finite task graph; the agent supplies scientific/engineering repairs.

The runner never invents successful outcomes or autonomously modifies source.
It diagnoses failures and emits ranked corrective actions for the next session.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import shutil
import time
from .model import Task, fingerprint, validate_graph
from .process import execute


def now():
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path, value):
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    os.replace(temp, path)


class Runner:
    def __init__(self, root, tasks, *, min_disk_bytes=2*1024**3,
                 max_log_bytes=1024**2, hardware_available=False):
        self.root = Path(root).resolve()
        self.tasks = validate_graph(tasks)
        self.min_disk_bytes = min_disk_bytes
        self.max_log_bytes = max_log_bytes
        self.hardware_available = hardware_available
        self.state_path = self.root/'PROJECT_STATE.json'
        self.evidence_dir = self.root/'artifacts'/'harness'
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {
            'schemaVersion': 1, 'project': 'GOLDEN MOTION',
            'directives': ['GM-ROOT-001', 'GM-RF-001'], 'createdAt': now(), 'tasks': {},
            'milestones': [], 'hypotheses': [], 'datasets': [], 'knownLimitations': [
                'No physical Galaxy A16 validation; builds and synthetic evidence are separate.']}
        self.state.setdefault('tasks', {})

    def save(self):
        self.state['updatedAt'] = now()
        atomic_json(self.state_path, self.state)

    def _refresh(self):
        for id, task in self.tasks.items():
            fp = fingerprint(self.root, task)
            entry = self.state['tasks'].get(id)
            missing_outputs = any(not (self.root/p).exists() for p in task.outputs)
            if entry is None or entry.get('fingerprint') != fp:
                self.state['tasks'][id] = {
                    'status': 'pending', 'attempts': 0, 'fingerprint': fp,
                    'evidence': entry.get('evidence', []) if entry else [],
                    'validation': 'implemented', 'evidence_kind': task.evidence_kind}
            elif entry.get('status') == 'passed' and missing_outputs:
                entry.update(status='pending', attempts=0)
            elif entry.get('status') == 'running':
                entry.update(status='pending')  # interrupted run; checkpoint remains
            if task.requires_hardware and not self.hardware_available:
                self.state['tasks'][id].update(status='blocked', failure_class='missing_resource',
                                               reason='Physical hardware unavailable')
            elif self.state['tasks'][id].get('status') == 'blocked':
                self.state['tasks'][id].update(status='pending')
        # Invalidating a producer invalidates already-passed downstream evidence.
        changed = True
        while changed:
            changed = False
            for id, task in self.tasks.items():
                entry = self.state['tasks'][id]
                if entry['status'] == 'passed' and any(
                    self.state['tasks'][dep]['status'] != 'passed' for dep in task.depends):
                    entry.update(status='pending', attempts=0)
                    changed = True
        self.save()

    def _next(self):
        ready = [task for id, task in self.tasks.items()
                 if self.state['tasks'][id]['status'] == 'pending'
                 and all(self.state['tasks'][d]['status'] == 'passed' for d in task.depends)]
        return sorted(ready, key=lambda t: (-t.priority, t.id))[0] if ready else None

    def _diagnose(self, task, result):
        text = result['output'].lower()
        kind = result['error'] or ('missing_resource' if any(x in text for x in [
            'command not found', 'no module named', 'enoent', 'sdk location not found',
            'could not resolve', 'network is unreachable']) else
            'scientific_hypothesis' if 'hypothesis_rejected' in text else 'engineering')
        descriptions = {
            'missing_resource': [('substitute', 'Use an available compatible tool or synthetic/recorded adapter', 0.9),
                                 ('repair', 'Inspect missing dependency or documented capability, then bootstrap', 0.8)],
            'resource_budget': [('diagnose', 'Inspect elapsed time, peak RSS and output; reduce batch size', 0.9),
                                ('substitute', 'Use smaller deterministic workload or offline cached build', 0.7)],
            'scientific_hypothesis': [('reformulate', 'Revisit identifiability and negative controls; preserve rejection', 0.95),
                                     ('redirect', 'Evaluate another observable feature or modality', 0.8)],
            'engineering': [('diagnose', 'Read evidence log and reproduce smallest failure', 0.95),
                            ('repair', 'Correct implementation/configuration and rerun failing check', 0.9)]}
        return kind, [{'level': level, 'action': action, 'priority': priority,
                       'validity': 'requires verification', 'cost': 'bounded',
                       'task': task.id} for level, action, priority in descriptions[kind]]

    def _execute(self, task, remaining_s):
        entry = self.state['tasks'][task.id]
        entry.update(status='running', startedAt=now(), attempts=entry['attempts']+1,
                     command=task.command, cwd=task.cwd)
        self.save()  # durable checkpoint BEFORE a command starts
        result = execute(task.command, self.root/task.cwd,
                         min(task.timeout_s, remaining_s), task.max_rss_mb, self.max_log_bytes)
        missing = [p for p in task.outputs if not (self.root/p).exists()]
        passed = result['returncode'] == 0 and not result['error'] and not missing
        log_name = f"{task.id}-{time.time_ns()}.txt"
        log_path = self.evidence_dir/log_name
        output = result['output'] + ('\nMissing artifacts: '+', '.join(missing) if missing else '')
        log_path.write_bytes(output.encode()[-self.max_log_bytes:])
        evidence = {k: v for k, v in result.items() if k != 'output'}
        evidence.update(timestamp=now(), command=task.command,
                        log=str(log_path.relative_to(self.root)),
                        fingerprint=entry['fingerprint'], passed=passed)
        entry['evidence'].append(evidence)
        entry.update(endedAt=now(), duration_s=result['duration_s'], returncode=result['returncode'],
                     peak_rss_mb=result['peak_rss_mb'])
        if passed:
            entry.update(status='passed', validation=task.validation,
                         failure_class=None, corrective_actions=[])
        else:
            kind, actions = self._diagnose(task, result)
            entry.update(status='pending' if entry['attempts'] <= task.retries else 'failed',
                         failure_class=kind, corrective_actions=actions)
        with (self.evidence_dir/'audit.jsonl').open('a') as stream:
            stream.write(json.dumps({'task': task.id, **evidence})+'\n')
        self.save()

    def run(self, *, max_tasks=20, budget_s=1800):
        if budget_s <= 0 or max_tasks < 0:
            raise ValueError('Execution budget must be positive')
        lock = (self.evidence_dir/'run.lock').open('w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            lock.close()
            raise RuntimeError('Another harness owns this project')
        executed, started = [], time.monotonic()
        try:
            self._refresh()
            stop = 'no_unblocked_tasks'
            while len(executed) < max_tasks:
                remaining = budget_s - (time.monotonic()-started)
                if remaining <= 0:
                    stop = 'time_budget'
                    break
                if shutil.disk_usage(self.root).free < self.min_disk_bytes:
                    stop = 'disk_reserve'
                    break
                task = self._next()
                if task is None:
                    break
                self._execute(task, remaining)
                executed.append(task.id)
            else:
                stop = 'task_budget'
            summary = {'executed': executed, 'stop_reason': stop,
                       'elapsed_s': time.monotonic()-started,
                       'counts': {s: sum(x['status'] == s for x in self.state['tasks'].values())
                                  for s in ['passed', 'failed', 'pending', 'blocked']}}
            self.state['lastRun'] = summary
            self.state['nextCandidateActions'] = [a for entry in self.state['tasks'].values()
                                                  for a in entry.get('corrective_actions', [])]
            self.save()
            return summary
        finally:
            lock.close()
