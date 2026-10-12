"""Behavior contracts: no retries forever, no success claims without evidence."""
import json
import os
import signal
from pathlib import Path
import sys
import tempfile
import unittest
from harness.runner import Runner, Task, fingerprint


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def task(self, name, code, **kw):
        return Task(id=name, command=[sys.executable, '-c', code], **kw)

    def test_dependency_order_overrides_priority(self):
        tasks = [self.task('consumer', "print('consumer')", depends=['producer'], priority=100),
                 self.task('producer', "print('producer')", priority=1)]
        r = Runner(self.root, tasks, min_disk_bytes=0)
        result = r.run(max_tasks=5, budget_s=10)
        self.assertEqual(result['executed'], ['producer', 'consumer'])
        self.assertEqual(r.state['tasks']['consumer']['status'], 'passed')

    def test_success_is_skipped_until_inputs_change(self):
        (self.root/'input.txt').write_text('first')
        task = self.task('stable', "print('ok')", inputs=['input.txt'])
        r = Runner(self.root, [task], min_disk_bytes=0)
        self.assertEqual(r.run(max_tasks=5, budget_s=10)['executed'], ['stable'])
        resumed = Runner(self.root, [task], min_disk_bytes=0)
        self.assertEqual(resumed.run(max_tasks=5, budget_s=10)['executed'], [])
        (self.root/'input.txt').write_text('changed')
        self.assertEqual(resumed.run(max_tasks=5, budget_s=10)['executed'], ['stable'])

    def test_failure_retries_are_bounded_and_preserved(self):
        task = self.task('failure', "raise RuntimeError('broken estimator')", retries=1)
        r = Runner(self.root, [task], min_disk_bytes=0)
        result = r.run(max_tasks=10, budget_s=10)
        self.assertEqual(result['executed'], ['failure', 'failure'])
        entry = r.state['tasks']['failure']
        self.assertEqual(entry['attempts'], 2)
        self.assertEqual(entry['status'], 'failed')
        self.assertEqual(entry['failure_class'], 'engineering')
        self.assertTrue(entry['evidence'])
        self.assertEqual(Runner(self.root, [task], min_disk_bytes=0).run(budget_s=1)['executed'], [])

    def test_timeout_kills_task_and_saves_checkpoint(self):
        r = Runner(self.root, [self.task('slow', 'import time; time.sleep(5)', timeout_s=0.1)], min_disk_bytes=0)
        r.run(max_tasks=2, budget_s=3)
        saved = json.loads((self.root/'PROJECT_STATE.json').read_text())
        self.assertEqual(saved['tasks']['slow']['status'], 'failed')
        self.assertEqual(saved['tasks']['slow']['failure_class'], 'resource_budget')
        self.assertLess(saved['tasks']['slow']['duration_s'], 2)

    def test_hardware_block_does_not_block_independent_task(self):
        tasks = [self.task('physical', "print('never')", requires_hardware=True),
                 self.task('simulation', "print('synthetic')")]
        r = Runner(self.root, tasks, min_disk_bytes=0)
        result = r.run(max_tasks=4, budget_s=5)
        self.assertEqual(result['executed'], ['simulation'])
        self.assertEqual(r.state['tasks']['physical']['status'], 'blocked')
        self.assertEqual(r.state['tasks']['physical']['failure_class'], 'missing_resource')

    def test_required_artifact_missing_is_failure_even_on_exit_zero(self):
        task = self.task('artifact', "print('built')", outputs=['missing.apk'])
        r = Runner(self.root, [task], min_disk_bytes=0)
        r.run(budget_s=5)
        self.assertEqual(r.state['tasks']['artifact']['status'], 'failed')

    def test_unknown_dependency_and_cycle_rejected(self):
        with self.assertRaises(ValueError):
            Runner(self.root, [self.task('a', 'pass', depends=['missing'])])
        with self.assertRaises(ValueError):
            Runner(self.root, [self.task('a','pass',depends=['b']),self.task('b','pass',depends=['a'])])

    def test_missing_executable_generates_resource_action(self):
        r = Runner(self.root, [Task(id='missing', command=['gm_missing_program_42'])], min_disk_bytes=0)
        r.run(budget_s=5)
        entry = r.state['tasks']['missing']
        self.assertEqual(entry['failure_class'], 'missing_resource')
        self.assertTrue(entry['corrective_actions'])

    def test_fingerprint_includes_command_and_file_content(self):
        (self.root/'a').write_text('1')
        a = self.task('same','print(1)',inputs=['a'])
        before = fingerprint(self.root,a)
        (self.root/'a').write_text('2')
        self.assertNotEqual(before, fingerprint(self.root,a))
        self.assertNotEqual(fingerprint(self.root,a),fingerprint(self.root,self.task('same','print(2)',inputs=['a'])))

    def test_output_truncation_preserves_bound(self):
        r = Runner(self.root,[self.task('loud', "print('x'*50000)")], min_disk_bytes=0, max_log_bytes=2048)
        r.run(budget_s=5)
        evidence = r.root / r.state['tasks']['loud']['evidence'][-1]['log']
        self.assertLessEqual(evidence.stat().st_size, 2048)

    def test_timeout_kills_a_descendant_that_ignores_termination(self):
        code = """import os,signal,time
from pathlib import Path
child=os.fork()
if child==0:
 signal.signal(signal.SIGTERM,signal.SIG_IGN)
 Path('child.pid').write_text(str(os.getpid()))
 time.sleep(30)
else:
 time.sleep(30)
"""
        r = Runner(self.root,[self.task('fork',code,timeout_s=.3)],min_disk_bytes=0)
        r.run(budget_s=5)
        pid=int((self.root/'child.pid').read_text())
        try:
            status=Path(f'/proc/{pid}/stat')
            self.assertTrue(not status.exists() or status.read_text().split()[2]=='Z',
                            'A surviving child violates the execution budget')
        finally:
            try: os.kill(pid,signal.SIGKILL)
            except ProcessLookupError: pass


if __name__ == '__main__':
    unittest.main()
