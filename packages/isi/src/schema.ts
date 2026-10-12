import type { ISIEvent, ISIEventType, Measurement, Zone } from './types';
const eventTypes: ISIEventType[] = ['hover','approach','retreat','swipe','scroll','hold','select','cancel','drag','rotate','zone-enter','zone-exit','motion-3d','motion-presence'];
export function finite(value: unknown, name: string): asserts value is number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new TypeError(`${name} must be finite`);
}
export function nonempty(value: unknown, name: string): asserts value is string {
  if (typeof value !== 'string' || !value.trim() || value.length > 256) throw new TypeError(`${name} must be a nonempty string of at most 256 characters`);
}
export function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}
function vec(value: unknown, name: string): void {
  if (!Array.isArray(value) || value.length !== 3) throw new TypeError(`${name} must have three components`);
  value.forEach(x => finite(x, name));
}
/** JSON-compatible, bounded provenance. Rejects cycles, nonfinite numbers and executable values. */
function json(value: unknown, depth = 0, budget = { count: 0 }): unknown {
  if (++budget.count > 4096 || depth > 12) throw new TypeError('metadata is too large or deeply nested');
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value;
  if (typeof value === 'number') { finite(value, 'metadata'); return value; }
  if (Array.isArray(value)) return value.map(v => json(v, depth + 1, budget));
  if (record(value)) {
    const result: Record<string, unknown> = {};
    for (const [key, entry] of Object.entries(value)) {
      if (key === '__proto__' || key === 'constructor' || key === 'prototype') throw new TypeError('unsafe metadata key');
      result[key] = json(entry, depth + 1, budget);
    }
    return result;
  }
  throw new TypeError('metadata must be JSON-compatible');
}
export function clone<T>(value: T): T { return JSON.parse(JSON.stringify(value)) as T; }
export function isMetricFrame(frame: string): boolean { return frame === 'phone-local-m' || frame === 'world-m' || frame.endsWith('-m'); }
export function validateMeasurement(input: unknown): Measurement {
  if (!record(input)) throw new TypeError('measurement must be an object');
  finite(input.timestamp, 'timestamp');
  if (input.timestamp < 0) throw new TypeError('timestamp must be nonnegative epoch milliseconds');
  finite(input.confidence, 'confidence');
  if (input.confidence < 0 || input.confidence > 1) throw new TypeError('confidence must be in [0,1]');
  if (!['synthetic', 'recorded', 'live'].includes(input.source as string)) throw new TypeError('source must declare provenance');
  for (const name of ['modality','deviceId','coordinateFrame']) nonempty(input[name], name);
  if (input.calibrationId !== undefined) nonempty(input.calibrationId, 'calibrationId');
  if (input.intent !== undefined && typeof input.intent !== 'boolean') throw new TypeError('intent must be boolean');
  if (input.position !== undefined) vec(input.position, 'position');
  if (input.velocity !== undefined) { vec(input.velocity, 'velocity'); if (!input.position) throw new TypeError('spatial velocity needs a position'); }
  const frame = input.coordinateFrame as string;
  if (frame === 'measurement-space' && input.position !== undefined) throw new TypeError('scalar measurements cannot claim spatial position');
  if (input.position !== undefined && !isMetricFrame(frame) && frame !== 'camera-image-normalized') throw new TypeError('position frame must declare metric or image units');
  if (frame === 'camera-image-normalized' && input.position !== undefined) {
    const p = input.position as number[];
    if (p[0] < 0 || p[0] > 1 || p[1] < 0 || p[1] > 1 || p[2] !== 0) throw new TypeError('image coordinates require x/y in [0,1] and zero depth');
    if (input.velocity !== undefined && (input.velocity as number[])[2] !== 0) throw new TypeError('image velocity cannot claim depth');
  }
  if (input.relative !== undefined) {
    if (!record(input.relative)) throw new TypeError('relative must be an object');
    nonempty(input.relative.kind, 'relative.kind'); nonempty(input.relative.unit, 'relative.unit'); finite(input.relative.value, 'relative.value');
    const kind = input.relative.kind as string;
    const unit = input.relative.unit;
    if ((kind.includes('range') || kind === 'distance') && (unit !== 'm' || input.relative.value < 0)) throw new TypeError('range must be nonnegative metres');
    if (frame === 'camera-image-normalized' && (unit !== 'normalized' || !['image-x','image-y'].includes(kind) || input.relative.value < 0 || input.relative.value > 1)) throw new TypeError('image scalar must be a normalized x/y coordinate in [0,1]');
    if (kind === 'rssi' && unit !== 'dBm') throw new TypeError('RSSI must use dBm');
    if (frame === 'measurement-space' && !['m','dBm','rad','m/s','Hz','unitless'].includes(unit as string)) throw new TypeError('unsupported measurement units');
  }
  if (!input.position && !input.relative) throw new TypeError('measurement must contain an observable position or scalar');
  if (frame === 'measurement-space' && !input.relative) throw new TypeError('measurement-space needs a scalar');
  if (input.uncertainty !== undefined) {
    const u = input.uncertainty;
    if (!Array.isArray(u) || u.length !== (input.position ? 3 : 1)) throw new TypeError('uncertainty must match observable dimensions');
    for (const x of u) { finite(x, 'uncertainty'); if (x < 0) throw new TypeError('uncertainty must be nonnegative standard deviations'); }
  }
  if (input.metadata !== undefined && !record(input.metadata)) throw new TypeError('metadata must be an object');
  const m: Measurement = {
    timestamp: input.timestamp, confidence: input.confidence, source: input.source as Measurement['source'],
    modality: input.modality as string, deviceId: input.deviceId as string, coordinateFrame: frame,
  };
  for (const key of ['position','velocity','relative','uncertainty','calibrationId','intent'] as const) {
    if (input[key] !== undefined) Object.assign(m, { [key]: clone(input[key]) });
  }
  if (input.metadata !== undefined) m.metadata = json(input.metadata) as Record<string, unknown>;
  return m;
}
export function validateEvent(input: unknown): ISIEvent {
  const m = validateMeasurement(input);
  if (!record(input)) throw new TypeError('event must be an object');
  nonempty(input.id, 'id');
  if (!eventTypes.includes(input.type as ISIEventType)) throw new TypeError('unknown event type');
  if (input.zoneId !== undefined) nonempty(input.zoneId, 'zoneId');
  if (input.interactionState !== undefined && !['idle','hovering','holding','selected','dragging','cancelled'].includes(input.interactionState as string)) throw new TypeError('unknown interactionState');
  if (input.type === 'motion-3d' && (!m.position || !isMetricFrame(m.coordinateFrame))) throw new TypeError('3D motion needs a metric spatial observation');
  if (m.relative?.kind === 'rssi' && !['motion-presence','cancel','zone-exit'].includes(input.type as string)) throw new TypeError('RSSI supports coarse motion presence only');
  const { intent: _intent, ...base } = m;
  return { ...base, id: input.id, type: input.type as ISIEventType,
    ...(input.zoneId === undefined ? {} : { zoneId: input.zoneId as string }),
    ...(input.interactionState === undefined ? {} : { interactionState: input.interactionState as ISIEvent['interactionState'] }) };
}
export function validateZones(zones: Zone[]): Zone[] {
  if (!Array.isArray(zones) || zones.length > 256) throw new TypeError('zones must be a bounded array');
  const ids = new Set<string>();
  for (const z of zones) {
    if (!record(z)) throw new TypeError('zone must be an object');
    nonempty(z.id, 'zone.id'); nonempty(z.frame, 'zone.frame');
    if (ids.has(z.id)) throw new TypeError('duplicate zone id'); ids.add(z.id);
    if (z.measurement) {
      if (z.center !== undefined || z.radius !== undefined || !['measurement-space','camera-image-normalized'].includes(z.frame)) throw new TypeError('scalar zone must use a declared measurement or image frame without spatial geometry');
      nonempty(z.measurement.kind, 'zone.measurement.kind'); finite(z.measurement.min, 'zone.min'); finite(z.measurement.max, 'zone.max');
      if (z.frame === 'camera-image-normalized' && (!['image-x','image-y'].includes(z.measurement.kind) || z.measurement.min < 0 || z.measurement.max > 1)) throw new TypeError('image interval must use normalized x/y bounds in [0,1]');
      if (z.measurement.min >= z.measurement.max) throw new TypeError('zone interval must be increasing');
    } else {
      vec(z.center, 'zone.center'); finite(z.radius, 'zone.radius');
      if (z.radius <= 0 || (!isMetricFrame(z.frame) && z.frame !== 'camera-image-normalized')) throw new TypeError('zone sphere must declare valid geometry and units');
    }
  }
  return clone(zones);
}
