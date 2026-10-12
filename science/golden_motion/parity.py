"""Execute independent kernels and compare actual numerical results to Python."""
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
import numpy as np
from .model import *

SCIENCE=Path(__file__).resolve().parents[1]
SCALAR_NAMES=['bistaticPathM','gradientX','gradientY','gradientZ','matchedRangeM','matchedCoherence','dopplerHz','radialVelocityMps','phaseDisplacementM','positionRank','stateRank']


def validate_outputs(reference,actual,*,atol=1e-9,rtol=1e-9):
    reference=np.asarray(reference); actual=np.asarray(actual)
    if reference.shape!=actual.shape or not np.isfinite(actual).all():
        return {'passed':False,'reason':'shape or nonfinite output','maxAbsError':None}
    error=np.abs(reference-actual)
    return {'passed':bool(np.all(error<=atol+rtol*np.abs(reference))),
            'maxAbsError':float(np.max(error)) if error.size else 0.,'atol':atol,'rtol':rtol}


def binary(language):
    env_name='JULIA_BIN' if language=='julia' else 'OCTAVE_BIN'
    if os.environ.get(env_name): return os.environ[env_name]
    available=shutil.which('julia' if language=='julia' else 'octave-cli')
    if available: return available
    local=SCIENCE/'.tools'/('julia-1.11.5/bin/julia' if language=='julia' else 'octave/bin/octave-cli')
    return str(local) if local.exists() else None


def run_parity():
    output=SCIENCE/'results'/'parity';output.mkdir(parents=True,exist_ok=True)
    cfg=AcousticConfig(noise_std=0); p=np.array([.1,.15,.23]);v=np.array([.01,-.02,.06])
    signal=simulate_echo(p,v,cfg); est=estimate_delay(signal,cfg)
    tone=simulate_tone(p,v,cfg,duration_s=.025);dop=estimate_doppler(tone,cfg)
    a=simulate_tone([0,0,.4],[0,0,0],cfg,duration_s=.001)
    b=simulate_tone([0,0,.401],[0,0,0],cfg,duration_s=.001)
    path,gradient=bistatic_path(p,[0,0,0],[0,0,0])
    anchors=np.array([[0,0,0],[.4,0,0],[0,.4,0],[0,0,.4]])
    ranks=observability(p,anchors,anchors)
    expected=np.r_[path,gradient,est['range_m'],est['confidence'],dop['frequency_hz'],dop['radial_velocity_m_s'],phase_displacement(a.received[0],b.received[0],cfg),ranks['position_rank'],ranks['state_rank']]
    echo=np.column_stack([signal.received.real,signal.received.imag])
    np.savetxt(output/'python-echo.csv',echo,delimiter=',');np.savetxt(output/'python-scalars.csv',expected,delimiter=',')
    report={'schemaVersion':1,'source':'synthetic','modelVersion':'gm-acoustics-v1','names':SCALAR_NAMES,'reference':expected.tolist(),'languages':{},'negativeControl':validate_outputs(expected,expected+1e-3)}
    for language,extension in [('julia','jl'),('octave','m')]:
        executable=binary(language)
        if not executable:
            report['languages'][language]={'passed':False,'status':'unavailable','hint':'Run bash science/bootstrap-tools.sh'};continue
        command=[executable]
        command+=['--startup-file=no'] if language=='julia' else ['--no-gui','--quiet']
        command+=[str(SCIENCE/'kernels'/f'acoustic.{extension}'),str(output)]
        env=os.environ.copy()
        prefix=Path(executable).resolve().parent.parent
        if language=='octave' and (prefix/'share'/'octave').exists():
            env['OCTAVE_HOME']=str(prefix)
        started=time.perf_counter(); proc=subprocess.run(command,capture_output=True,text=True,timeout=120,env=env)
        version=subprocess.run([executable,'--version'],capture_output=True,text=True,timeout=15).stdout.splitlines()[0]
        item={'status':'executed','command':command,'version':version,'exitCode':proc.returncode,'elapsedS':time.perf_counter()-started,'stdout':proc.stdout,'stderr':proc.stderr}
        if proc.returncode==0:
            scalar=np.loadtxt(output/f'{language}-scalars.csv',delimiter=',').reshape(-1)
            generated_echo=np.loadtxt(output/f'{language}-echo.csv',delimiter=',')
            item['scalars']=validate_outputs(expected,scalar);item['signal']=validate_outputs(echo,generated_echo)
            item['outputs']=scalar.tolist();item['passed']=item['scalars']['passed'] and item['signal']['passed']
        else: item['passed']=False
        report['languages'][language]=item
    report['passed']=all(item['passed'] for item in report['languages'].values())
    (SCIENCE/'results'/'parity.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def main():
    report=run_parity(); print(json.dumps(report,indent=2));raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__':main()
