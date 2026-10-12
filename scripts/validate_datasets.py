"""Validate provenance, finite values, monotonic clocks and fixture dimensions."""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def finite_tree(value, path='$'):
    if isinstance(value,float) and not math.isfinite(value):
        raise ValueError('Nonfinite value at '+path)
    if isinstance(value,dict):
        for k,v in value.items(): finite_tree(v,path+'.'+k)
    elif isinstance(value,list):
        for i,v in enumerate(value): finite_tree(v,path+f'[{i}]')


def validate_fixture(data):
    finite_tree(data)
    if data.get('source') != 'synthetic' or not data.get('modelVersion') or not isinstance(data.get('seed'),int):
        raise ValueError('Generated fixture must identify synthetic source/model/seed')
    frames = data.get('frames')
    if not frames or len(frames)>100000:
        raise ValueError('Fixture needs a bounded, nonempty frame array')
    previous = -math.inf
    for frame in frames:
        ts = frame['timestampMs']
        if not isinstance(ts,(int,float)) or ts<=previous:
            raise ValueError('Fixture timestamps must be strictly increasing')
        previous=ts
        truth=frame['truth']
        if len(truth['positionM'])!=3 or len(truth['velocityMps'])!=3:
            raise ValueError('Ground truth needs declared 3D frame dimensions')
        acoustic=frame['acoustic']
        if acoustic.get('coordinateFrame')!='measurement-space' or 'position' in acoustic:
            raise ValueError('Scalar acoustic estimate cannot become 3D coordinates')
        optical=frame['optical']
        if optical.get('depthObserved') is not False:
            raise ValueError('Monocular synthetic optical fixture has no measured depth')
        for modality in ['acoustic','optical','fused','ble']:
            if frame.get(modality,{}).get('source')!='synthetic':
                raise ValueError('Generated fixture has mixed/unknown evidence provenance')
    return {'frames':len(frames), 'source':'synthetic','model':data['modelVersion'],'seed':data['seed']}


def main():
    rows=[]
    fixture=ROOT/'science/results/browser-fixture.json'
    rows.append({'path':str(fixture.relative_to(ROOT)),**validate_fixture(json.loads(fixture.read_text())),
                 'sha256':hashlib.sha256(fixture.read_bytes()).hexdigest()})
    for name in ['experiments.json','classifiers.json']:
        p=ROOT/'science/rf/results'/name
        data=json.loads(p.read_text());finite_tree(data)
        if data.get('provenance')!='synthetic' or data.get('physical_tested') is not False:
            raise ValueError('RF synthetic experiments must not become physical evidence')
        rows.append({'path':str(p.relative_to(ROOT)),'source':'synthetic',
                     'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
    (ROOT/'artifacts/dataset-validation.json').write_text(json.dumps({'passed':True,'datasets':rows},indent=2)+'\n')
    print(json.dumps(rows,indent=2))


if __name__=='__main__':
    main()
