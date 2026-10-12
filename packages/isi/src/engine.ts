import type { EngineOptions, EventListener, ISIEvent, ISIEventType, Measurement, MeasurementAdapter, SubscriptionFilter, Zone } from './types';
import { clone, finite, isMetricFrame, validateMeasurement, validateZones } from './schema';
import { evaluateZone } from './zones';
interface ActiveZone { stableSince: number; held: boolean; selected: boolean }
interface DeviceState {
  last: Measurement; zones: Map<string, ActiveZone>; intentSince?: number;
  cooldowns: Map<string, number>;
}
interface AdapterState { adapter: MeasurementAdapter; running: boolean; generation: number; cleanup?: () => void; pending?: Promise<void> }
const defaults = { minConfidence: 0.6, dwellMs: 350, cooldownMs: 200, hysteresis: 0.015,
  dropoutMs: 500, debounceMs: 80, maxAgeMs: Infinity, liveMaxAgeMs: 1000, maxFutureMs: 1000, uncertaintySigma: 2,
  minMotionSpeed: 0.04, swipeSpeed: 0.6, scrollScale: 1000, maxScrollDelta: 120 };
/** Deterministic, framework-independent inference. Call tick from the host's clock to detect silent dropout. */
export class InteractionEngine {
  private readonly options: typeof defaults;
  private readonly now: () => number;
  private zones: Zone[];
  private devices = new Map<string, DeviceState>();
  private subscribers = new Set<{ listener: EventListener; filter: SubscriptionFilter }>();
  private adapters = new Map<string, AdapterState>();
  private sequence = 0;
  private disposed = false;
  private stopping = new Map<string, Promise<void>>();
  constructor(options: EngineOptions = {}) {
    this.options = { ...defaults, ...options };
    this.now = options.now ?? Date.now;
    for (const [key, value] of Object.entries(this.options)) {
      if (!(key in defaults)) continue;
      if (key === 'maxAgeMs' && value === Infinity) continue;
      finite(value, key);
      if (value < 0) throw new TypeError(`${key} must be nonnegative`);
    }
    if (this.options.minConfidence > 1) throw new TypeError('minConfidence must be in [0,1]');
    this.zones = validateZones(options.zones ?? []);
  }
  subscribe(listener: EventListener, filter: SubscriptionFilter = {}): () => void {
    if (this.disposed) throw new Error('engine is disposed');
    if (typeof listener !== 'function') throw new TypeError('listener must be a function');
    if (filter.minConfidence !== undefined && (!Number.isFinite(filter.minConfidence) || filter.minConfidence < 0 || filter.minConfidence > 1)) throw new TypeError('invalid subscription confidence');
    const subscription = { listener, filter: clone(filter) };
    this.subscribers.add(subscription);
    return () => { this.subscribers.delete(subscription); };
  }
  private publish(events: ISIEvent[]): ISIEvent[] {
    for (const event of events) for (const { listener, filter } of [...this.subscribers]) {
      if ((filter.types && !filter.types.includes(event.type)) ||
        (filter.deviceId && filter.deviceId !== event.deviceId) ||
        (filter.zoneId && filter.zoneId !== event.zoneId) ||
        (filter.modality && filter.modality !== event.modality) ||
        (filter.source && filter.source !== event.source) ||
        (filter.minConfidence !== undefined && event.confidence < filter.minConfidence)) continue;
      // A consumer cannot corrupt inference or another consumer's event; exceptions are isolated.
      try { listener(clone(event)); } catch { /* Subscriber errors belong to the host. */ }
    }
    return events;
  }
  private event(m: Measurement, type: ISIEventType, zoneId?: string, state?: ISIEvent['interactionState'], metadata?: Record<string, unknown>): ISIEvent {
    const { intent: _intent, ...base } = clone(m);
    return { ...base, id: `${m.deviceId}:${m.timestamp}:${++this.sequence}`, type,
      ...(zoneId ? { zoneId } : {}), ...(state ? { interactionState: state } : {}),
      ...(metadata ? { metadata: { ...base.metadata, ...metadata } } : {}) };
  }
  private releaseState(state: DeviceState, timestamp: number, reason: string, zoneId?: string): ISIEvent[] {
    const m = { ...state.last, timestamp: Math.max(timestamp, state.last.timestamp) };
    const result: ISIEvent[] = [];
    for (const [id, active] of state.zones) {
      if (zoneId && id !== zoneId) continue;
      if (active.selected) result.push(this.event(m, 'cancel', id, 'cancelled', { reason }));
      result.push(this.event(m, 'zone-exit', id, 'idle', { reason }));
      state.zones.delete(id);
    }
    return result;
  }
  updateZones(zones: Zone[]): void {
    const next = validateZones(zones);
    const events: ISIEvent[] = [];
    // Release geometry even when an id is retained: old dwell cannot authorize a new target.
    for (const state of this.devices.values()) events.push(...this.releaseState(state, state.last.timestamp, 'zones-updated'));
    this.zones = next;
    this.publish(events);
  }
  /** Explicit host stop: publish releases before discarding device history. */
  release(timestamp = this.now(), reason = 'explicit-stop'): ISIEvent[] {
    finite(timestamp, 'release timestamp');
    const events: ISIEvent[] = [];
    for (const state of this.devices.values()) events.push(...this.releaseState(state, timestamp, reason));
    this.devices.clear();
    return this.publish(events);
  }
  /** Silent reset for independent replay. Hosts stopping active input should call release instead. */
  reset(): void { this.devices.clear(); }
  tick(timestamp = this.now()): ISIEvent[] {
    finite(timestamp, 'tick timestamp');
    const events: ISIEvent[] = [];
    for (const [id, state] of this.devices) if (timestamp - state.last.timestamp > this.options.dropoutMs) {
      events.push(...this.releaseState(state, timestamp, 'dropout'));
      this.devices.delete(id);
    }
    return this.publish(events);
  }
  ingest(input: Measurement): ISIEvent[] {
    if (this.disposed) return [];
    let m: Measurement;
    try { m = validateMeasurement(input); } catch {
      // Reject the payload, but release subscribers using only the last validated observation.
      if (input && typeof input.deviceId === 'string') {
        const state = this.devices.get(input.deviceId);
        if (state) {
          this.devices.delete(input.deviceId);
          this.publish(this.releaseState(state, state.last.timestamp, 'invalid-input'));
        }
      }
      return [];
    }
    let state = this.devices.get(m.deviceId);
    const events: ISIEvent[] = [];
    const now = this.now(); finite(now, 'engine clock');
    // A live stream must align with the host epoch, independently of replay age policy.
    const maxPast = m.source === 'live' ? Math.min(this.options.maxAgeMs, this.options.liveMaxAgeMs) : this.options.maxAgeMs;
    const maxFuture = m.source === 'live' ? Math.min(this.options.maxAgeMs, this.options.maxFutureMs) : this.options.maxAgeMs;
    const temporalReason = now - m.timestamp > maxPast ? 'stale' : m.timestamp - now > maxFuture ? 'future-timestamp' : undefined;
    if (temporalReason) {
      // Never promote rejected timestamp data into history or lifecycle event timestamps.
      if (state) events.push(...this.releaseState(state, now, temporalReason));
      this.devices.delete(m.deviceId);
      return this.publish(events);
    }
    if (state && m.timestamp <= state.last.timestamp) return [];
    if (m.confidence < this.options.minConfidence) {
      if (state) events.push(...this.releaseState(state, m.timestamp, 'low-confidence'));
      this.devices.delete(m.deviceId);
      return this.publish(events);
    }
    if (state && (m.timestamp - state.last.timestamp > this.options.dropoutMs || m.modality !== state.last.modality ||
      m.coordinateFrame !== state.last.coordinateFrame || m.source !== state.last.source || m.calibrationId !== state.last.calibrationId ||
      m.relative?.kind !== state.last.relative?.kind || m.relative?.unit !== state.last.relative?.unit)) {
      events.push(...this.releaseState(state, m.timestamp, 'observation-discontinuity'));
      this.devices.delete(m.deviceId); state = undefined;
    }
    const previous = state?.last;
    if (!state) {
      if (this.devices.size >= 256) {
        const oldest = this.devices.entries().next().value as [string, DeviceState];
        events.push(...this.releaseState(oldest[1], m.timestamp, 'device-capacity'));
        this.devices.delete(oldest[0]);
      }
      state = { last: m, zones: new Map(), cooldowns: new Map() };
      this.devices.set(m.deviceId, state);
    }
    const dt = previous ? (m.timestamp - previous.timestamp) / 1000 : 0;
    const delta = previous?.position && m.position ? m.position.map((v, i) => v - previous.position![i]) : undefined;
    const derivedVelocity = delta && dt > 0 ? delta.map(v => v / dt) as Measurement['velocity'] : undefined;
    const velocity = m.velocity ?? derivedVelocity;
    const spatialSpeed = velocity ? Math.hypot(...velocity) : 0;
    const scalarDelta = previous?.relative && m.relative ? m.relative.value - previous.relative.value : 0;
    const scalarSpeed = dt > 0 ? scalarDelta / dt : 0;
    const speed = m.position ? spatialSpeed : Math.abs(scalarSpeed);
    if (derivedVelocity && isMetricFrame(m.coordinateFrame)) m = { ...m, velocity: derivedVelocity };
    if (m.intent) state.intentSince ??= m.timestamp;
    else {
      state.intentSince = undefined;
      for (const [id, active] of state.zones) if (active.selected) {
        events.push(this.event(m, 'cancel', id, 'cancelled', { reason: 'intent-released' }));
        active.selected = false; active.stableSince = m.timestamp; active.held = false;
      }
    }
    const intentional = m.intent === true && m.timestamp - (state.intentSince ?? m.timestamp) >= this.options.debounceMs;
    const allowed = (type: ISIEventType, zoneId = '') => {
      const key = `${type}:${zoneId}`;
      const last = state!.cooldowns.get(key);
      if (last !== undefined && m.timestamp - last < this.options.cooldownMs) return false;
      state!.cooldowns.set(key, m.timestamp); return true;
    };
    // RSSI is deliberately never routed to range, zones, scroll or spatial inference.
    if (m.relative?.kind === 'rssi') {
      if (previous && Math.abs(scalarDelta) > Math.max(1, ...(m.uncertainty ?? []), ...(previous.uncertainty ?? [])))
        events.push(this.event(m, 'motion-presence', undefined, 'idle', { rssiDeltaDb: scalarDelta, coarse: true }));
      state.last = m;
      return this.publish(events);
    }
    let activationObservable = this.zones.length === 0;
    for (const zone of this.zones) {
      const membership = evaluateZone(m, zone, this.options.uncertaintySigma);
      let active = state.zones.get(zone.id);
      if (active && (membership.quality === 'unobservable' ||
        (membership.signedDistance !== undefined && membership.signedDistance > this.options.hysteresis))) {
        events.push(...this.releaseState(state, m.timestamp, 'outside-zone', zone.id)); active = undefined;
      }
      if (!active && membership.quality === 'inside') {
        active = { stableSince: m.timestamp, held: false, selected: false };
        state.zones.set(zone.id, active);
        events.push(this.event(m, 'zone-enter', zone.id, 'hovering'));
      }
      if (!active) continue;
      if (membership.quality === 'inside') activationObservable = true;
      events.push(this.event(m, 'hover', zone.id, active.selected ? 'selected' : active.held ? 'holding' : 'hovering'));
      if (speed > this.options.minMotionSpeed || membership.quality !== 'inside') {
        active.stableSince = m.timestamp;
        if (!active.selected) active.held = false;
      }
      const stable = membership.quality === 'inside' && speed <= this.options.minMotionSpeed && m.timestamp - active.stableSince >= this.options.dwellMs;
      if (stable && !active.held) { active.held = true; events.push(this.event(m, 'hold', zone.id, 'holding')); }
      if (stable && intentional && !active.selected && allowed('select', zone.id)) {
        active.selected = true; events.push(this.event(m, 'select', zone.id, 'selected'));
      }
      if (active.selected && intentional && membership.quality === 'inside' && speed > this.options.minMotionSpeed && delta) {
        events.push(this.event(m, 'drag', zone.id, 'dragging', { delta, units: isMetricFrame(m.coordinateFrame) ? 'm' : 'normalized' }));
        if (zone.center && previous?.position && m.position) {
          const a = [previous.position[0] - zone.center[0], previous.position[1] - zone.center[1]];
          const b = [m.position[0] - zone.center[0], m.position[1] - zone.center[1]];
          const angle = Math.atan2(a[0] * b[1] - a[1] * b[0], a[0] * b[0] + a[1] * b[1]);
          if (Math.hypot(...a) > 0.01 && Math.hypot(...b) > 0.01 && Math.abs(angle) > 0.03 && allowed('rotate', zone.id))
            events.push(this.event(m, 'rotate', zone.id, 'dragging', { angleRad: angle }));
        }
      }
    }
    if (previous && speed > this.options.minMotionSpeed) {
      if (m.position && isMetricFrame(m.coordinateFrame)) events.push(this.event(m, 'motion-3d', undefined, undefined, { speedMps: speed }));
      const radialVelocity = m.position ? velocity?.[2] ?? 0 : m.relative?.unit === 'm' ? scalarSpeed : 0;
      if (Math.abs(radialVelocity) > this.options.minMotionSpeed)
        events.push(this.event(m, radialVelocity < 0 ? 'approach' : 'retreat', undefined, undefined,
          m.position ? { radialVelocityMps: radialVelocity } : { measurementVelocity: { value: scalarSpeed, unit: 'm/s', kind: m.relative!.kind } }));
      if (intentional && activationObservable) {
        const amount = m.position ? delta?.[1] ?? 0 : m.relative?.unit === 'm' ? -scalarDelta : m.coordinateFrame === 'camera-image-normalized' && m.relative?.unit === 'normalized' ? scalarDelta : 0;
        if (Math.abs(amount) > 0 && allowed('scroll')) {
          const scrollDelta = Math.max(-this.options.maxScrollDelta, Math.min(this.options.maxScrollDelta, amount * this.options.scrollScale));
          events.push(this.event(m, 'scroll', undefined, undefined, { scrollDelta, unit: 'px', intentional: true }));
        }
        if (m.position && spatialSpeed > this.options.swipeSpeed && allowed('swipe'))
          events.push(this.event(m, 'swipe', undefined, undefined, { direction: delta }));
      }
    }
    state.last = m;
    return this.publish(events);
  }
  registerAdapter(adapter: MeasurementAdapter): () => Promise<void> {
    if (this.disposed) throw new Error('engine is disposed');
    if (!adapter || !adapter.id || typeof adapter.start !== 'function' || this.adapters.has(adapter.id)) throw new TypeError('adapter requires a unique id and start function');
    if (this.adapters.size >= 256) throw new RangeError('adapter capacity exceeded');
    this.adapters.set(adapter.id, { adapter, running: false, generation: 0 });
    return async () => { await this.stopAdapter(adapter.id); this.adapters.delete(adapter.id); };
  }
  async startAdapter(id: string): Promise<void> {
    const previousStop = this.stopping.get(id);
    if (previousStop) await previousStop;
    const a = this.adapters.get(id);
    if (!a || this.disposed) throw new Error('adapter not registered or engine disposed');
    if (a.running) return a.pending;
    a.running = true; const generation = ++a.generation;
    a.pending = (async () => {
      try {
        const cleanup = await a.adapter.start(m => { if (a.running && generation === a.generation && !this.disposed) this.ingest({ ...m, metadata: { ...m.metadata, adapterId: id } }); });
        if (typeof cleanup === 'function') {
          if (a.running && generation === a.generation) a.cleanup = cleanup;
          else cleanup();
        }
      } catch (error) {
        if (generation === a.generation) { a.running = false; this.releaseAdapter(id, 'adapter-start-failed'); }
        throw error;
      }
    })();
    return a.pending;
  }
  private releaseAdapter(id: string, reason: string): void {
    const events: ISIEvent[] = [];
    for (const [deviceId, state] of this.devices) if (state.last.metadata?.adapterId === id) {
      events.push(...this.releaseState(state, state.last.timestamp, reason)); this.devices.delete(deviceId);
    }
    this.publish(events);
  }
  async stopAdapter(id: string): Promise<void> {
    const existing = this.stopping.get(id); if (existing) return existing;
    const a = this.adapters.get(id);
    if (!a || !a.running) return;
    a.running = false; ++a.generation;
    this.releaseAdapter(id, 'adapter-stopped');
    const pending = a.pending;
    const stopping = (async () => {
      try { a.cleanup?.(); } finally { a.cleanup = undefined; await a.adapter.stop?.(); }
      await pending;
    })();
    this.stopping.set(id, stopping);
    try { await stopping; } finally { this.stopping.delete(id); }
  }
  async dispose(): Promise<void> {
    this.disposed = true;
    try { await Promise.all([...this.adapters.keys()].map(id => this.stopAdapter(id))); }
    finally { this.reset(); this.subscribers.clear(); this.adapters.clear(); }
  }
}
