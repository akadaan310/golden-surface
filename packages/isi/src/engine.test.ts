import { describe, expect, it, vi } from 'vitest';
import { InteractionEngine, evaluateZone, syntheticMeasurement, validateEvent, validateMeasurement } from './index';
import type { ISIEvent, Measurement, Zone } from './index';

const sample = (timestamp = 1_000, extra: Partial<Measurement> = {}): Measurement => ({
  timestamp, source: 'synthetic', modality: 'simulated-hand', deviceId: 'phone-1',
  coordinateFrame: 'phone-local-m', confidence: 0.95, position: [0, 0, 0.1],
  uncertainty: [0.001, 0.001, 0.001], ...extra,
});
const zone: Zone = { id: 'target', frame: 'phone-local-m', center: [0, 0, 0.1], radius: 0.2 };
const types = (events: ISIEvent[]) => events.map(event => event.type);

describe('runtime schema', () => {
  it('accepts a spatial measurement and complete semantic event', () => {
    expect(validateMeasurement(sample()).position).toEqual([0, 0, 0.1]);
    expect(validateEvent({ ...sample(), id: 'event-1', type: 'hover' }).type).toBe('hover');
  });
  it.each([
    { timestamp: Infinity }, { confidence: 1.1 }, { confidence: NaN }, { position: [0, 0] },
    { velocity: [0, Infinity, 0] }, { uncertainty: [-1, 0, 0] }, { uncertainty: [0, 0] },
    { source: 'guessed' }, { intent: 'yes' }, { metadata: [] },
    { coordinateFrame: 'measurement-space' },
    { coordinateFrame: 'camera-image-normalized', position: [0.2, 0.3, 1] },
  ])('rejects malformed sample %j', extra => {
    expect(() => validateMeasurement({ ...sample(), ...extra })).toThrow();
  });
  it('permits scalar range without creating a position', () => {
    const m = validateMeasurement(sample(1_000, { coordinateFrame: 'measurement-space', position: undefined, uncertainty: [0.02], relative: { kind: 'bistatic-range', value: 0.4, unit: 'm' } }));
    expect(m.position).toBeUndefined();
  });
  it('rejects scalar measurement without observable units and invalid semantics', () => {
    expect(() => validateMeasurement({ ...sample(), coordinateFrame: 'measurement-space', position: undefined, uncertainty: [0.1], relative: { kind: 'bistatic-range', value: 2, unit: 'px' } })).toThrow();
    expect(() => validateEvent({ ...sample(), id: 'bad', type: 'teleport' })).toThrow();
    expect(() => validateEvent({ ...sample(), type: 'hover' })).toThrow();
  });
});

describe('observable zone membership', () => {
  it('treats uncertainty crossing the boundary as uncertain', () => {
    expect(evaluateZone(sample(1_000, { position: [0.19, 0, 0.1], uncertainty: [0.02, 0, 0] }), zone).quality).toBe('uncertain');
    expect(evaluateZone(sample(), zone).inside).toBe(true);
  });
  it('evaluates scalar ranges only against matching measurement zones', () => {
    const m = sample(1_000, { position: undefined, coordinateFrame: 'measurement-space', uncertainty: [0.01], relative: { kind: 'bistatic-range', value: 0.4, unit: 'm' } });
    expect(evaluateZone(m, zone).quality).toBe('unobservable');
    expect(evaluateZone(m, { id: 'near', frame: 'measurement-space', measurement: { kind: 'bistatic-range', min: 0.2, max: 0.6 } }).inside).toBe(true);
  });
});

describe('interaction inference', () => {
  it('enters and holds but selects only after intentional stable dwell', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 100, debounceMs: 20 });
    expect(types(engine.ingest(sample()))).toContain('zone-enter');
    expect(types(engine.ingest(sample(1_100)))).toContain('hold');
    expect(types(engine.ingest(sample(1_120)))).not.toContain('select');
    expect(types(engine.ingest(sample(1_140, { intent: true })))).not.toContain('select');
    expect(types(engine.ingest(sample(1_170, { intent: true })))).toContain('select');
    expect(types(engine.ingest(sample(1_200, { intent: true })))).not.toContain('select');
  });
  it('gates scroll on intent and confidence', () => {
    const engine = new InteractionEngine({ zones: [zone], debounceMs: 0 });
    engine.ingest(sample());
    const moving = { position: [0, 0.02, 0.1] as [number, number, number] };
    expect(types(engine.ingest(sample(1_100, moving)))).not.toContain('scroll');
    expect(types(engine.ingest(sample(1_200, { position: [0, 0.04, 0.1], intent: true })))).toContain('scroll');
    expect(types(engine.ingest(sample(1_300, { position: [0, 0.06, 0.1], intent: true, confidence: 0.1 })))).not.toContain('scroll');
  });
  it('holds an active zone through hysteresis and exits beyond it', () => {
    const engine = new InteractionEngine({ zones: [zone], hysteresis: 0.03 });
    engine.ingest(sample());
    expect(types(engine.ingest(sample(1_100, { position: [0.21, 0, 0.1], uncertainty: [0, 0, 0] })))).not.toContain('zone-exit');
    expect(types(engine.ingest(sample(1_200, { position: [0.25, 0, 0.1], uncertainty: [0, 0, 0] })))).toContain('zone-exit');
  });
  it('releases state on dropout, low confidence and modality change', () => {
    const engine = new InteractionEngine({ zones: [zone], dropoutMs: 200 });
    engine.ingest(sample());
    expect(types(engine.tick(1_201))).toContain('zone-exit');
    engine.ingest(sample(1_300));
    expect(types(engine.ingest(sample(1_400, { confidence: 0 })))).toContain('zone-exit');
    engine.ingest(sample(1_500));
    expect(types(engine.ingest(sample(1_600, { modality: 'another-sensor' })))).toContain('zone-exit');
  });
  it('rejects out-of-order, stale and invalid input without actions', () => {
    const engine = new InteractionEngine({ zones: [zone], maxAgeMs: 500, now: () => 1_200 });
    engine.ingest(sample());
    expect(engine.ingest(sample(999, { intent: true }))).toEqual([]);
    expect(engine.ingest(sample(1_100, { position: [NaN, 0, 0] }))).toEqual([]);
    expect(new InteractionEngine({ maxAgeMs: 100, now: () => 2_000 }).ingest(sample())).toEqual([]);
  });
  it('infers radial approach without claiming acoustic 3D', () => {
    const engine = new InteractionEngine({ debounceMs: 0 });
    const m = sample(1_000, { position: undefined, uncertainty: [0.01], coordinateFrame: 'measurement-space', modality: 'rf-bistatic', relative: { kind: 'bistatic-range', value: 0.5, unit: 'm' } });
    engine.ingest(m);
    const events = engine.ingest({ ...m, timestamp: 1_100, intent: true, relative: { ...m.relative!, value: 0.45 } });
    expect(types(events)).toContain('approach');
    expect(types(events)).toContain('scroll');
    expect(types(events)).not.toContain('motion-3d');
    expect(events.every(event => event.position === undefined)).toBe(true);
  });
  it('maps RSSI change to coarse presence only', () => {
    const engine = new InteractionEngine({ debounceMs: 0 });
    const m = sample(1_000, { position: undefined, uncertainty: [1], coordinateFrame: 'measurement-space', modality: 'rf-rssi', intent: true, relative: { kind: 'rssi', value: -50, unit: 'dBm' } });
    engine.ingest(m);
    expect(types(engine.ingest({ ...m, timestamp: 1_100, relative: { ...m.relative!, value: -42 } }))).toEqual(['motion-presence']);
  });
  it('subscriptions unsubscribe and reset allows independent replay ordering', () => {
    const engine = new InteractionEngine({ zones: [zone] });
    const received: ISIEvent[] = [];
    const off = engine.subscribe(event => received.push(event));
    engine.ingest(sample());
    expect(received.length).toBeGreaterThan(0);
    off(); const count = received.length;
    engine.reset(); engine.ingest(sample());
    expect(received).toHaveLength(count);
  });
});

describe('deterministic simulator', () => {
  it('repeats seeded noise and declares synthetic provenance', () => {
    const m = syntheticMeasurement(200, { seed: 7, noise: 0.02, timestamp: 1_000 });
    expect(m).toEqual(syntheticMeasurement(200, { seed: 7, noise: 0.02, timestamp: 1_000 }));
    expect(m.source).toBe('synthetic');
    expect(validateMeasurement(m).position).toHaveLength(3);
    expect(() => syntheticMeasurement(NaN)).toThrow();
  });
});

describe('safety and reusable SDK lifecycle', () => {
  it('releases selected state when malformed data is received', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 0, debounceMs: 0 });
    expect(types(engine.ingest(sample(1_000, { intent: true })))).toContain('select');
    engine.ingest(sample(1_010, { position: [NaN, 0, 0] }));
    expect(types(engine.ingest(sample(1_020, { position: [0.03, 0, 0.1], intent: true })))).not.toContain('drag');
  });
  it('keeps device histories independent and cancels selected state on intent release', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 0, debounceMs: 0 });
    engine.ingest(sample(1_000, { intent: true }));
    expect(types(engine.ingest(sample(900, { deviceId: 'phone-2' })))).toContain('zone-enter');
    expect(types(engine.ingest(sample(1_100, { intent: false })))).toContain('cancel');
  });
  it('requires stable dwell again after motion and ignores uncertainty-only entry', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 100, debounceMs: 0 });
    engine.ingest(sample());
    expect(types(engine.ingest(sample(1_100, { position: [0.1, 0, 0.1], intent: true })))).not.toContain('select');
    expect(types(engine.ingest(sample(1_201, { position: [0.1, 0, 0.1], intent: true })))).toContain('select');
    const uncertain = new InteractionEngine({ zones: [zone] });
    expect(types(uncertain.ingest(sample(1_000, { position: [0.19, 0, 0.1], uncertainty: [0.02, 0, 0] })))).not.toContain('zone-enter');
  });
  it('never emits spatial motion from camera-image coordinates', () => {
    const engine = new InteractionEngine({ debounceMs: 0 });
    engine.ingest(sample(1_000, { coordinateFrame: 'camera-image-normalized', position: [0.2, 0.3, 0] }));
    const events = engine.ingest(sample(1_100, { coordinateFrame: 'camera-image-normalized', position: [0.4, 0.3, 0], intent: true }));
    expect(types(events)).not.toContain('motion-3d');
    expect(() => validateEvent({ ...sample(), coordinateFrame: 'measurement-space', position: undefined, uncertainty: [0.1], relative: { kind: 'rssi', value: -50, unit: 'dBm' }, type: 'motion-3d', id: 'bad' })).toThrow();
  });
  it('allows filtered subscriptions and isolates subscriber mutation', () => {
    const engine = new InteractionEngine({ zones: [zone] });
    const events: ISIEvent[] = [];
    engine.subscribe(event => { event.type = 'cancel'; });
    engine.subscribe(event => events.push(event), { types: ['zone-enter'], deviceId: 'phone-1' });
    const result = engine.ingest(sample());
    expect(events.map(e => e.type)).toEqual(['zone-enter']);
    expect(types(result)).toContain('zone-enter');
  });
  it('rejects invalid zone definitions and engine thresholds', () => {
    expect(() => new InteractionEngine({ zones: [{ ...zone, radius: -1 }] })).toThrow();
    expect(() => new InteractionEngine({ dwellMs: -1 })).toThrow();
    expect(() => new InteractionEngine({ zones: [zone, zone] })).toThrow();
  });
});

describe('gesture authorization and cooldown', () => {
  it('drags and rotates only a deliberately selected target', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 0, debounceMs: 0 });
    engine.ingest(sample(1_000, { position: [0.08, 0, 0.1], intent: true }));
    const selected = engine.ingest(sample(1_100, { position: [0, 0.08, 0.1], intent: true }));
    expect(types(selected)).toContain('drag'); expect(types(selected)).toContain('rotate');
    const released = engine.ingest(sample(1_200, { position: [-0.08, 0, 0.1], intent: false }));
    expect(types(released)).toContain('cancel'); expect(types(released)).not.toContain('drag');
    expect(types(released)).not.toContain('rotate'); expect(types(released)).not.toContain('scroll');
  });
  it('suppresses repeated select actions within the cooldown', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 0, debounceMs: 0, cooldownMs: 1_000, dropoutMs: 5_000 });
    expect(types(engine.ingest(sample(1_000, { intent: true })))).toContain('select');
    engine.ingest(sample(1_100, { intent: false }));
    expect(types(engine.ingest(sample(1_200, { intent: true })))).not.toContain('select');
    expect(types(engine.ingest(sample(2_000, { intent: true })))).toContain('select');
  });
});

describe('explicit host release', () => {
  it('publishes cancel and zone-exit, preserving source and frame on stop', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 0, debounceMs: 0 });
    engine.ingest(sample(1_000, { intent: true }));
    const events = engine.release(1_100);
    expect(types(events)).toEqual(['cancel', 'zone-exit']);
    expect(events.every(e => e.source === 'synthetic' && e.coordinateFrame === 'phone-local-m')).toBe(true);
    expect(engine.tick(2_000)).toEqual([]);
  });
});

describe('activation boundaries and invalid-input release', () => {
  it('does not scroll or swipe outside configured zones despite intent', () => {
    const engine = new InteractionEngine({ zones: [zone], debounceMs: 0 });
    engine.ingest(sample(1000, { position: [0.4, 0, 0.1], intent: true }));
    const events = engine.ingest(sample(1100, { position: [0.4, 0.1, 0.1], intent: true }));
    expect(types(events)).toContain('motion-3d');
    expect(types(events)).not.toContain('scroll'); expect(types(events)).not.toContain('swipe');
  });
  it('retains hover but suppresses actions in an uncertain hysteresis shell', () => {
    const engine = new InteractionEngine({ zones: [zone], debounceMs: 0, dwellMs: 0, hysteresis: 0.03 });
    engine.ingest(sample(1000, { position: [0.18, 0, 0.1], intent: true }));
    const events = engine.ingest(sample(1100, { position: [0.19, 0.03, 0.1], uncertainty: [0.02,0.02,0.02], intent: true }));
    expect(types(events)).toContain('hover'); expect(types(events)).not.toContain('zone-exit');
    for (const forbidden of ['scroll','swipe','drag','rotate','select']) expect(types(events)).not.toContain(forbidden);
  });
  it('publishes validated release events to subscribers on malformed payload', () => {
    const engine = new InteractionEngine({ zones: [zone], dwellMs: 0, debounceMs: 0 });
    engine.ingest(sample(1000, { intent: true }));
    const events: ISIEvent[] = []; engine.subscribe(e => events.push(e));
    expect(engine.ingest(sample(1100, { position: [NaN,0,0] }))).toEqual([]);
    expect(types(events)).toEqual(['cancel','zone-exit']);
    expect(events.every(e => e.metadata?.reason === 'invalid-input')).toBe(true);
    events.forEach(e => expect(validateEvent(e).position).toEqual([0,0,0.1]));
  });
});

describe('synthetic timestamp contract', () => {
  it('uses a reproducible epoch origin by default and validates generation options', () => {
    const first = syntheticMeasurement(200);
    expect(first.timestamp).toBeGreaterThan(1_000_000_000_000);
    expect(first).toEqual(syntheticMeasurement(200));
    expect(() => syntheticMeasurement(200, { deviceId: '' })).toThrow();
  });
});

describe('live timestamp safety', () => {
  const now = 1_800_000_000_000;
  it.each([-86_400_000, 400 * 86_400_000])('rejects live timestamp offset %s with safe defaults', offset => {
    const engine = new InteractionEngine({ zones: [zone], now: () => now, dwellMs: 0, debounceMs: 0 });
    expect(engine.ingest(sample(now + offset, { source: 'live', intent: true }))).toEqual([]);
    expect(engine.ingest(sample(now, { source: 'live', intent: true })).map(e => e.type)).toContain('select');
    expect(types(engine.tick(now + 1_000))).toEqual(['cancel','zone-exit']);
  });
  it('releases existing state with trusted clock time and does not poison ordering', () => {
    const engine = new InteractionEngine({ zones: [zone], now: () => now, dwellMs: 0, debounceMs: 0 });
    engine.ingest(sample(now, { source: 'live', intent: true }));
    const released = engine.ingest(sample(now + 400 * 86_400_000, { source: 'live', intent: true }));
    expect(types(released)).toEqual(['cancel','zone-exit']);
    expect(released.every(e => e.timestamp === now && e.metadata?.reason === 'future-timestamp')).toBe(true);
    expect(types(engine.ingest(sample(now + 10, { source: 'live', intent: true })))).toContain('zone-enter');
  });
  it('keeps replay independent while Infinity does not disable live freshness', () => {
    const engine = new InteractionEngine({ zones: [zone], now: () => now, maxAgeMs: Infinity, dwellMs: 0, debounceMs: 0 });
    expect(types(engine.ingest(sample(1_000, { source: 'synthetic', intent: true })))).toContain('select');
    engine.reset();
    expect(types(engine.ingest(sample(now + 86_400_000, { source: 'recorded', intent: true })))).toContain('select');
    engine.reset();
    expect(engine.ingest(sample(now - 86_400_000, { source: 'live', intent: true }))).toEqual([]);
    expect(() => new InteractionEngine({ liveMaxAgeMs: Infinity })).toThrow();
    expect(() => new InteractionEngine({ maxFutureMs: Infinity })).toThrow();
  });
  it('permits explicitly configured finite live clock tolerances', () => {
    const engine = new InteractionEngine({ zones: [zone], now: () => now, liveMaxAgeMs: 2_000, maxFutureMs: 200 });
    expect(types(engine.ingest(sample(now - 1_500, { source: 'live' })))).toContain('zone-enter');
    engine.reset();
    expect(engine.ingest(sample(now + 201, { source: 'live' }))).toEqual([]);
  });
});

describe('normalized camera measurement regions', () => {
  it('activates an image-y interval and intentionally scrolls without reconstructing depth', () => {
    const imageZone: Zone = { id: 'image-band', frame: 'camera-image-normalized', measurement: { kind: 'image-y', min: 0.25, max: 0.75 } };
    const engine = new InteractionEngine({ zones: [imageZone], debounceMs: 0 });
    const camera = sample(1000, { position: undefined, coordinateFrame: 'camera-image-normalized', relative: { kind: 'image-y', value: 0.5, unit: 'normalized' }, uncertainty: [0.01], intent: true });
    expect(types(engine.ingest(camera))).toContain('zone-enter');
    const events = engine.ingest({ ...camera, timestamp: 1100, relative: { ...camera.relative!, value: 0.55 } });
    expect(types(events)).toContain('scroll'); expect(types(events)).not.toContain('motion-3d');
    expect(types(events)).not.toContain('approach'); expect(events.every(e => !e.position && !e.velocity)).toBe(true);
    expect(() => validateMeasurement({ ...camera, relative: { kind: 'image-y', value: 0.5, unit: 'm' } })).toThrow();
  });
});
