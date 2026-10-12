import json
from pathlib import Path
import sys
import tempfile
import unittest
from harness.config import load_tasks, exclude_tasks
from harness.model import Task,validate_graph


class ConfigurationTests(unittest.TestCase):
    def test_installed_virtual_environment_controls_scientific_interpreter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'harness').mkdir();(root/'.venv/bin').mkdir(parents=True)
            (root/'.venv/bin/python').touch()
            (root/'harness/tasks.json').write_text(json.dumps({'tasks':[{'id':'science','command':['python3','model.py']}]}))
            self.assertEqual(load_tasks(root)[0].command[0],str(root/'.venv/bin/python'))
    def test_current_interpreter_used_without_virtual_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'harness').mkdir()
            (root/'harness/tasks.json').write_text(json.dumps({'tasks':[{'id':'science','command':['python3','model.py']}]}))
            self.assertEqual(load_tasks(root)[0].command[0],sys.executable)
    def test_quick_graph_removes_transitive_dependents_of_excluded_builds(self):
        tasks=[Task('sdk',['true']),Task('android',['true'],depends=['sdk']),
               Task('phone',['true'],depends=['android'],requires_hardware=True)]
        quick=exclude_tasks(tasks,['android'])
        self.assertEqual([t.id for t in quick],['sdk'])
        validate_graph(quick)
