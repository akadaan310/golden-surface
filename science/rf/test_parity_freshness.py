"""Stale scientific output must not survive source changes or missing languages."""
import unittest,tempfile,json,shutil,subprocess,sys
from pathlib import Path
import parity
class FreshParityTests(unittest.TestCase):
 def prepare(self,temp):
  root=Path(temp)/'project';rf=root/'science/rf';(rf/'results').mkdir(parents=True)
  original=Path(__file__).resolve().parent;manifest=json.loads((original/'results/language-execution.json').read_text())
  for name in manifest['sources']:
   dest=root/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(original.parents[1]/name,dest)
  for name in ['language-execution.json','julia-kernel.csv','octave-kernel.csv','typescript-kernel.json']:
   shutil.copy(original/'results'/name,rf/'results'/name)
  return root,rf
 def test_changed_Julia_source_rejects_cached_outputs(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,rf=self.prepare(tmp);(rf/'kernel.jl').write_text('intentionally invalid Julia source')
   old=parity.ROOT;parity.ROOT=rf
   try:
    with self.assertRaisesRegex(AssertionError,'Current source differs'):parity.main()
   finally:parity.ROOT=old
 def test_missing_tools_are_pending_exit_not_success(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,rf=self.prepare(tmp)
   r=subprocess.run([sys.executable,str(rf/'parity_runner.py')],cwd=root,capture_output=True,text=True,timeout=5)
   self.assertEqual(r.returncode,3,r.stderr)
   self.assertEqual(json.loads((rf/'results/parity.json').read_text())['status'],'pending_tool')
 def test_failed_language_execution_replaces_cached_pass(self):
  with tempfile.TemporaryDirectory() as tmp:
   root,rf=self.prepare(tmp);(rf/'results/parity.json').write_text('{"status":"passed"}')
   binary=root/'science/.tools/julia-1.11.5/bin/julia';binary.parent.mkdir(parents=True);binary.write_text('#!/bin/sh\nexit 7\n');binary.chmod(0o700)
   r=subprocess.run([sys.executable,str(rf/'parity_runner.py')],cwd=root,capture_output=True,text=True,timeout=5)
   self.assertNotEqual(r.returncode,0);self.assertEqual(json.loads((rf/'results/parity.json').read_text())['status'],'failed_execution')
if __name__=='__main__':unittest.main()
