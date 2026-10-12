"""Bounded reproducible RF execution. Optional public source fetch is separate."""
from pathlib import Path
import subprocess,sys,json,time,os
ROOT=Path(__file__).resolve().parents[2];RF=Path(__file__).resolve().parent

def main():
 log=[]
 tasks=[[sys.executable,str(RF/'test_rf.py')],[sys.executable,str(RF/'test_acquisition.py')],[sys.executable,str(RF/'test_tcp_budget.py')],[sys.executable,str(RF/'test_classifiers.py')],[sys.executable,str(RF/'experiments.py')],[sys.executable,str(RF/'classifiers.py')],[sys.executable,str(RF/'fusion.py')],[sys.executable,str(RF/'test_statistics.py')],[sys.executable,str(RF/'parity_runner.py')],[sys.executable,str(RF/'test_parity_freshness.py')]]
 for args in tasks:
  start=time.monotonic();r=subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=120)
  log.append({'command':args,'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-start,'stdout_last_500':r.stdout[-500:],'stderr_last_500':r.stderr[-500:]})
  print(Path(args[1]).name,r.returncode,round(log[-1]['elapsed_seconds'],3))
  if r.returncode:break
 (RF/'results/execution.json').write_text(json.dumps({'provenance':'synthetic','physical_tested':False,'tasks':log},indent=2)+'\n')
 return int(any(v['exit_code'] for v in log))
if __name__=='__main__':sys.exit(main())
