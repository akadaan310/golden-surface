"""Copy explicitly synthetic experimental evidence into the local browser lab."""
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
target=ROOT/'apps/web/public/fixtures'
target.mkdir(parents=True,exist_ok=True)
for source,name in [('science/results/browser-fixture.json','acoustic-optical.json'),
                    ('science/rf/results/experiments.json','rf-results.json'),
                    ('science/rf/results/classifiers.json','rf-classifiers.json')]:
    p=ROOT/source
    if p.exists(): shutil.copyfile(p,target/name)
print('Copied explicitly synthetic experiment fixtures into apps/web/public/fixtures')
