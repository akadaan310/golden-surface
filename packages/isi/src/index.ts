export * from './types';
export { validateMeasurement, validateEvent } from './schema';
export { evaluateZone } from './zones';
export { InteractionEngine } from './engine';
import type { Measurement } from './types';
import { finite, validateMeasurement } from './schema';
/** Deterministic synthetic data; no sensor measurements or physical inference are implied. */
export function syntheticMeasurement(elapsedMs: number, options: { noise?: number; seed?: number; deviceId?: string; timestamp?: number; intent?: boolean } = {}): Measurement {
  finite(elapsedMs, 'elapsedMs');
  const noise = options.noise ?? 0; finite(noise, 'noise');
  const seed = options.seed ?? 1; finite(seed, 'seed');
  const timestamp = options.timestamp ?? (1_700_000_000_000 + elapsedMs); finite(timestamp, 'timestamp');
  if (elapsedMs < 0 || timestamp < 0 || noise < 0) throw new TypeError('synthetic time and noise must be nonnegative');
  let state = (seed ^ Math.round(elapsedMs)) >>> 0;
  const random = () => { state = (Math.imul(1664525, state) + 1013904223) >>> 0; return state / 4294967296; };
  const t = elapsedMs / 1000;
  return validateMeasurement({ timestamp, source: 'synthetic', modality: 'simulated-hand', deviceId: options.deviceId ?? 'synthetic-phone',
    coordinateFrame: 'phone-local-m', confidence: 0.95,
    position: [0.10 * Math.sin(t) + noise * (random() * 2 - 1), 0.08 * Math.cos(t * 0.7) + noise * (random() * 2 - 1), 0.14 + 0.04 * Math.sin(t * 0.5) + noise * (random() * 2 - 1)],
    uncertainty: [noise / Math.sqrt(3), noise / Math.sqrt(3), noise / Math.sqrt(3)], intent: options.intent ?? false,
    metadata: { evidence: 'deterministic synthetic trajectory; no hardware measurement', seed } });
}
export { applyCalibration, validateCalibration, CalibrationRegistry } from './calibration';
export { replayMeasurements } from './replay';
