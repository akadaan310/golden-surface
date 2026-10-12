import { describe, expect, it } from 'vitest';
import { InteractionEngine, applyCalibration, CalibrationRegistry, replayMeasurements, validateMeasurement } from './index';
import type { CalibrationTransform, ISIEvent, Measurement } from './index';
const m = (timestamp: number, extra: Partial<Measurement> = {}): Measurement => ({
  timestamp, source: 'synthetic', modality: 'test', deviceId: 'd', coordinateFrame: 'phone-local-m',
  confidence: 0.9, position: [0.1, 0.02, 0.1], uncertainty: [0.01, 0.02, 0.03], ...extra,
});
const transform: CalibrationTransform = { id: 'c', fromFrame: 'phone-local-m', toFrame: 'world-m',
  rotation: [0,-1,0,1,0,0,0,0,1], translation: [1,2,3] };

describe('bounded reproducible replay', () => {
  it('bounds a potentially infinite iterable and preserves acquisition provenance', () => {
    function* stream() { let t = 1000; while (true) { yield m(t); t += 100; } }
    const engine = new InteractionEngine({ zones: [{ id: 'z', frame: 'phone-local-m', center: [0,0,0.1], radius: 0.3 }] });
    const first = replayMeasurements(engine, stream(), { maxSamples: 3 });
    expect(first.samples).toBe(3); expect(first.truncated).toBe(true);
    expect(first.events[0].source).toBe('recorded');
    expect(first.events[0].metadata?.originalSource).toBe('synthetic');
    expect(first.events[0].metadata?.replay).toBe(true);
    const second = replayMeasurements(engine, [m(1000)], { maxSamples: 3 });
    expect(second.events.some(e => e.type === 'zone-enter')).toBe(true);
  });
  it('bounds replay duration and event count and rejects invalid budgets', () => {
    const engine = new InteractionEngine({ zones: [{ id: 'z', frame: 'phone-local-m', center: [0,0,0.1], radius: 0.3 }] });
    expect(replayMeasurements(engine, [m(1000), m(2000)], { maxDurationMs: 100 }).samples).toBe(1);
    const result = replayMeasurements(engine, [m(1000)], { maxEvents: 1 });
    expect(result.events).toHaveLength(1); expect(result.truncated).toBe(true);
    expect(() => replayMeasurements(engine, [], { maxSamples: Infinity })).toThrow();
  });
});

describe('explicit metric calibration', () => {
  it('rotates position, velocity and independent-axis standard deviations', () => {
    const result = applyCalibration(m(1000, { velocity: [1,0,0] }), transform);
    expect(result.position).toEqual([0.98,2.1,3.1]);
    expect(result.velocity).toEqual([0,1,0]); expect(result.uncertainty).toEqual([0.02,0.01,0.03]);
    expect(result.calibrationId).toBe('c'); expect(result.source).toBe('synthetic');
    expect(result.coordinateFrame).toBe('world-m'); expect(validateMeasurement(result)).toEqual(result);
    const registry = new CalibrationRegistry(); registry.register(transform);
    expect(registry.apply(m(1000), 'c').position).toEqual(result.position);
    registry.remove('c'); expect(() => registry.apply(m(1000), 'c')).toThrow();
  });
  it('rejects scale, reflection, image/scalar lift and frame mismatch', () => {
    expect(() => applyCalibration(m(1000), { ...transform, rotation: [2,0,0,0,1,0,0,0,1] })).toThrow();
    expect(() => applyCalibration(m(1000), { ...transform, rotation: [-1,0,0,0,1,0,0,0,1] })).toThrow();
    expect(() => applyCalibration(m(1000, { coordinateFrame: 'camera-image-normalized', position: [0.1,0.2,0] }), { ...transform, fromFrame: 'camera-image-normalized' })).toThrow();
    expect(() => applyCalibration(m(1000, { coordinateFrame: 'world-m' }), transform)).toThrow();
    expect(() => applyCalibration(m(1000, { coordinateFrame: 'measurement-space', position: undefined, uncertainty: [0.01], relative: { kind: 'range', value: 0.2, unit: 'm' } }), transform)).toThrow();
  });
});

describe('adapter lifecycle', () => {
  it('starts once, stops emission, releases zones, and unregisters', async () => {
    const engine = new InteractionEngine({ zones: [{ id: 'z', frame: 'phone-local-m', center: [0,0,0.1], radius: 0.3 }] });
    let emit!: (measurement: Measurement) => void; let starts = 0; let stops = 0;
    const events: ISIEvent[] = []; engine.subscribe(e => events.push(e));
    const unregister = engine.registerAdapter({ id: 'test', start: cb => { starts++; emit = cb; return () => { stops++; }; } });
    await engine.startAdapter('test'); await engine.startAdapter('test'); emit(m(1000));
    expect(starts).toBe(1); expect(events.some(e => e.type === 'zone-enter')).toBe(true);
    await engine.stopAdapter('test'); expect(stops).toBe(1); expect(events.at(-1)?.type).toBe('zone-exit');
    const count = events.length; emit(m(1100)); expect(events).toHaveLength(count);
    await unregister(); await expect(engine.startAdapter('test')).rejects.toThrow();
  });
  it('cleans up a start that resolves after stop and ignores late callbacks', async () => {
    const engine = new InteractionEngine(); let release!: (cleanup: () => void) => void;
    let cleanupCount = 0; let emit!: (measurement: Measurement) => void;
    engine.registerAdapter({ id: 'slow', start: cb => { emit = cb; return new Promise(resolve => { release = resolve; }); } });
    const starting = engine.startAdapter('slow'); const stopping = engine.stopAdapter('slow');
    release(() => { cleanupCount++; }); await starting; await stopping;
    expect(cleanupCount).toBe(1); emit(m(1000)); expect(engine.tick(2000)).toEqual([]);
    await engine.dispose(); expect(() => engine.subscribe(() => {})).toThrow();
  });
});

describe('adapter failure release', () => {
  it('releases emitted state when start rejects and also when cleanup throws', async () => {
    const engine = new InteractionEngine({ zones: [{ id: 'z', frame: 'phone-local-m', center: [0,0,0.1], radius: 0.3 }] });
    const events: ISIEvent[] = []; engine.subscribe(e => events.push(e));
    engine.registerAdapter({ id: 'fail', start: emit => { emit(m(1000)); return Promise.reject(new Error('device failed')); } });
    await expect(engine.startAdapter('fail')).rejects.toThrow('device failed');
    expect(events.at(-1)?.type).toBe('zone-exit');
    engine.registerAdapter({ id: 'cleanup-fail', start: emit => { emit(m(2000)); return () => { throw new Error('cleanup failed'); }; } });
    await engine.startAdapter('cleanup-fail');
    await expect(engine.stopAdapter('cleanup-fail')).rejects.toThrow('cleanup failed');
    expect(events.at(-1)?.type).toBe('zone-exit');
  });
});
