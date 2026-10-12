"""Execute current Julia/Octave/TS sources, fingerprint them, then compare outputs.
Missing language tools return3 (pending), never a successful parity claim.
"""
from pathlib import Path
import subprocess,os,json,sys,hashlib
ROOT=Path(__file__).resolve().parents[2];RF=Path(__file__).parent
commands={'julia':ROOT/'science/.tools/julia-1.11.5/bin/julia','octave':ROOT/'science/.tools/octave/bin/octave-cli'}
log={}
for name,binary in commands.items():
 if not binary.exists():log[name]={'status':'pending_tool','binary':str(binary)};continue
 env=os.environ.copy()
 if name=='octave':env['OCTAVE_HOME']=str(binary.parent.parent)
 args=[str(binary),'--startup-file=no',str(RF/'kernel.jl')] if name=='julia' else [str(binary),'--quiet','--no-gui',str(RF/'kernel.m')]
 r=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
 log[name]={'command':args,'exit_code':r.returncode,'stderr':r.stderr[-1000:],'output_sha256':hashlib.sha256(r.stdout.encode()).hexdigest()}
 if r.returncode:
  failure={'languages':log,'status':'failed_execution'}
  (RF/'results/language-execution.json').write_text(json.dumps(failure,indent=2)+'\n');(RF/'results/parity.json').write_text(json.dumps(failure,indent=2)+'\n');raise RuntimeError(log[name])
 (RF/'results'/f'{name}-kernel.csv').write_text(r.stdout)
typescript_code="import {defaultRfConfig,generateCsiFrame} from './packages/rf/src/index.ts';const c=defaultRfConfig();c.subcarriers=3;c.noiseStd=0;c.phaseNoiseRad=0;c.packetLoss=0;c.clockDriftPpm=0;console.log(JSON.stringify([0,.1,.3].map(t=>generateCsiFrame(t,c))));"
node=subprocess.run(['node','--experimental-strip-types','--input-type=module','-e',typescript_code],cwd=ROOT,capture_output=True,text=True,timeout=30)
log['typescript']={'command':['node','--experimental-strip-types','--input-type=module','-e','<fixed parity fixture>'],'exit_code':node.returncode,'stderr':node.stderr[-1000:],'output_sha256':hashlib.sha256(node.stdout.encode()).hexdigest()}
if node.returncode:
 failure={'languages':log,'status':'failed_execution'}
 (RF/'results/language-execution.json').write_text(json.dumps(failure,indent=2)+'\n');(RF/'results/parity.json').write_text(json.dumps(failure,indent=2)+'\n');raise RuntimeError(log['typescript'])
(RF/'results/typescript-kernel.json').write_text(node.stdout)
sources={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in [RF/'kernel.py',RF/'kernel.jl',RF/'kernel.m',RF/'parity.py',RF/'parity_runner.py',ROOT/'packages/rf/src/index.ts']}
complete=all(log[name].get('exit_code')==0 for name in ('julia','octave','typescript'))
(RF/'results/language-execution.json').write_text(json.dumps({'languages':log,'sources':sources,'python_executable':sys.executable,'status':'executed_current_sources' if complete else 'pending_tool'},indent=2)+'\n')
if not complete:
 (RF/'results/parity.json').write_text(json.dumps({'status':'pending_tool','languages':log},indent=2)+'\n');print('RF language parity pending missing tool; no cached result accepted');sys.exit(3)
# Invoke the comparison with the same interpreter, not an unrelated python alias.
result=subprocess.run([sys.executable,str(RF/'parity.py')],cwd=ROOT,timeout=60)
sys.exit(result.returncode)
