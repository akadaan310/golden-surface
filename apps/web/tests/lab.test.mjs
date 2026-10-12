import { test } from 'node:test';
import assert from 'node:assert/strict';
import { acousticExperiment, magneticExperiment, safeAction, defaults, pointInZone } from '../lib/lab.ts';

test('acoustic forward model estimates a generated delay rather than copying truth', () => {
 const clean = acousticExperiment({...defaults, noise:0, multipath:0, drift:0}, 700, [.04,.10,.24]);
 assert.equal(clean.source, 'synthetic');
 assert.ok(clean.samples.some(x=>x!==0));
 assert.ok(Math.abs(clean.estimate-clean.truth)<.008);
 assert.ok(clean.coordinateFrame==='measurement-space');
 assert.equal(clean.position, undefined);
});
test('seeded perturbations repeat and waveform noise changes estimation evidence', () => {
 const a=acousticExperiment({...defaults,noise:.5},500,[0,.10,.30]);
 const b=acousticExperiment({...defaults,noise:.5},500,[0,.10,.30]);
 assert.deepEqual(a,b);
 const clean=acousticExperiment({...defaults,noise:0},500,[0,.10,.30]);
 assert.notDeepEqual(a.samples,clean.samples);
 assert.ok(a.uncertainty>clean.uncertainty);
});
test('dropout and absent hand withhold estimate and confidence', () => {
 const dropout=acousticExperiment({...defaults,dropout:1},900,[0,.10,.20]);
 assert.equal(dropout.estimate, null);
 assert.equal(dropout.confidence,0);
 const absent=acousticExperiment({...defaults,handPresent:false},900,[0,.10,.20]);
 assert.equal(absent.estimate,null);
});
test('intent confidence and current sensing are all required for semantic actions', () => {
 const s={running:true,intent:true,confidence:.8,dropout:false,zone:true};
 assert.equal(safeAction(s),true);
 for(const change of [{intent:false},{confidence:.1},{running:false},{dropout:true},{zone:false}]) assert.equal(safeAction({...s,...change}),false);
});
test('magnetic model is scalar and marked simulated capability',()=>{
 const result=magneticExperiment(defaults,700,[0,.1,.2]);
 assert.equal(result.coordinateFrame,'measurement-space');
 assert.equal(result.position,undefined);
 assert.ok(Number.isFinite(result.estimate));
});
test('zone editor changes membership using explicit phone-local proxy coordinates',()=>{
 assert.equal(pointInZone([0,0,.2],[0,0,.2],.1),true);
 assert.equal(pointInZone([0,0,.2],[.4,0,.2],.1),false);
});
test('competing observed echo peaks reduce confidence and increase uncertainty',()=>{
 const clean=acousticExperiment({...defaults,noise:0,multipath:0},500,[0,.11,.22]);
 const ambiguous=acousticExperiment({...defaults,noise:0,multipath:1},500,[0,.11,.22]);
 assert.ok(ambiguous.confidence<clean.confidence);
 assert.ok(ambiguous.uncertainty>clean.uncertainty);
 assert.ok(Math.abs(ambiguous.error)>.05);
});
