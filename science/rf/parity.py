"""Validate independent Julia/Octave kernels against analytical Python model."""
import json,csv,hashlib
from pathlib import Path
import numpy as np
from kernel import RFConfig,csi_forward,estimate_rssi
ROOT=Path(__file__).parent
def main():
 manifest=json.loads((ROOT/'results/language-execution.json').read_text())
 assert manifest.get('status')=='executed_current_sources','Run parity_runner.py: fresh executions required'
 for relative,digest in manifest['sources'].items():
  assert hashlib.sha256((ROOT.parents[1]/relative).read_bytes()).hexdigest()==digest, 'Current source differs from executed source: '+relative
 for language in ('julia','octave','typescript'):
  path=ROOT/'results'/('typescript-kernel.json' if language=='typescript' else language+'-kernel.csv')
  assert hashlib.sha256(path.read_bytes()).hexdigest()==manifest['languages'][language]['output_sha256'],'Output changed since language execution'
 c=RFConfig(subcarriers=3,sample_hz=10,noise=0,phase_noise=0,packet_loss=0,clock_drift_ppm=0)
 t,h,_,_=csi_forward(c,duration=.4,seed=1);out={}
 for language in ['julia','octave']:
  path=ROOT/'results'/f'{language}-kernel.csv'
  if not path.exists():out[language]={'status':'pending_tool'};continue
  errors=[];distance=None;rank=None
  for row in csv.reader(path.open()):
   if row[0]=='CSI':
    ts=float(row[1]);a,k=int(row[2]),int(row[3]);value=complex(float(row[4]),float(row[5]));errors.append(abs(value-h[round(ts*10),a,k]))
   if row[0]=='RSSI':distance=float(row[1])
   if row[0]=='RANK':rank=int(row[1])
  assert len(errors)==18 and max(errors)<1e-10,(language,errors)
  assert abs(distance-2)<1e-12 and rank==1,(language,distance,rank)
  out[language]={'status':'passed','complex_values_compared':len(errors),'maximum_absolute_complex_error':float(max(errors)),'rssi_inverse_distance_m':distance,'single_link_fisher_rank':rank,'noise':'disabled for deterministic mathematical parity; not stochastic simulator equivalence'}
 ts=json.loads((ROOT/'results/typescript-kernel.json').read_text());errors=[]
 for frame,i in zip(ts,[0,1,3]):
  hh=np.array([[complex(z['re'],z['im']) for z in row] for row in frame['csi']]);errors.append(float(np.max(np.abs(hh-h[i]))))
 assert len(errors)==3 and max(errors)<1e-10
 out['typescript']={'status':'passed','complex_values_compared':18,'maximum_absolute_complex_error':max(errors),'stochastic_parity':'not asserted; PRNGs differ'}
 (ROOT/'results/parity.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
