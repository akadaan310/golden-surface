import {test} from 'node:test';
import assert from 'node:assert/strict';
const api = await import('../src/index.ts').catch(()=>null);
test('common CFO never becomes inferred position or motion',()=>{
 assert.ok(api, 'RF API missing');
 const c=api.defaultRfConfig(); c.reflectors[0].velocity=[0,0,0]; c.cfoHz=40;
 const e=api.analyzeCsi(api.simulateRf(c,{durationS:4,seed:2}),c);
 assert.equal(e.presence,false); assert.equal('position' in e,false);
});
test('moving reflector returns scalar motion evidence',()=>{
 assert.ok(api, 'RF API missing'); const c=api.defaultRfConfig();
 const e=api.analyzeCsi(api.simulateRf(c,{durationS:4,seed:1}),c);
 assert.equal(e.presence,true); assert.ok(e.pathRateMps!>0); assert.equal('position' in e,false);
});
test('RSSI pipeline rejects CSI and does not invent radial velocity',()=>{
 assert.ok(api,'RF API missing'); const c=api.defaultRfConfig();
 const e=api.analyzeRssi(api.extractRssiSamples(api.simulateRf(c,{durationS:10})),c);
 assert.equal('pathRateMps' in e,false); assert.equal('radialVelocityMps' in e,false);
});
test('deterministic stream and explicit loss',()=>{
 assert.ok(api,'RF API missing'); const c=api.defaultRfConfig(); c.packetLoss=.3;
 assert.deepEqual(api.simulateRf(c,{seed:42}),api.simulateRf(c,{seed:42}));
 assert.ok(api.simulateRf(c,{seed:42}).some(f=>f.lost));
});
test('ISI adapter preserves measurement space and requires explicit intent',()=>{
 assert.ok(api,'RF API missing'); const c=api.defaultRfConfig();
 const e=api.analyzeCsi(api.simulateRf(c),c),m=api.rfMeasurement(e,{timestamp:123});
 assert.equal(m.coordinateFrame,'measurement-space');assert.equal(m.intent,false);
 assert.equal('position' in m,false);assert.equal(m.relative.kind,'rf-motion-score');
});
test('RF adapter validates in the shared SDK including absent Doppler', async()=>{
 assert.ok(api,'RF API missing');
 const {validateMeasurement}=await import('../../isi/src/schema.ts');
 const c=api.defaultRfConfig();c.reflectors[0].velocity=[0,0,0];
 const e=api.analyzeCsi(api.simulateRf(c),c);
 assert.doesNotThrow(()=>validateMeasurement(api.rfMeasurement(e,{timestamp:123})));
});
test('RF model rejects nonfinite geometry and nuisance values',()=>{
 assert.ok(api,'RF API missing');const c=api.defaultRfConfig();c.reflectors[0].velocity[0]=NaN;
 assert.throws(()=>api.generateCsiFrame(0,c));
 const d=api.defaultRfConfig();d.phaseNoiseRad=NaN;assert.throws(()=>api.generateCsiFrame(0,d));
});
test('Doppler diagnostics expose calculated spectrum and cancel common phase',()=>{
 assert.ok(api,'RF API missing');assert.ok(api.csiDiagnostics,'RF diagnostics missing');
 const c=api.defaultRfConfig();c.noiseStd=0;c.phaseNoiseRad=0;c.reflectors[0].velocity=[0,0,0];
 const a=api.csiDiagnostics(api.simulateRf(c),c);c.cfoHz=43;
 const b=api.csiDiagnostics(api.simulateRf(c),c);
 assert.equal(a.spectrumHz.length,a.spectrumPower.length);assert.ok(a.spectrumHz.length>0);
 assert.ok(a.trace.length>20);assert.equal(a.trace.length,b.trace.length);
 for(let i=0;i<a.trace.length;i++)assert.ok(Math.hypot(a.trace[i].re-b.trace[i].re,a.trace[i].im-b.trace[i].im)<1e-10);
});
