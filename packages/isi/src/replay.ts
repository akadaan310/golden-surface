import type { ISIEvent, Measurement, ReplayOptions, ReplayResult } from './types';
import { InteractionEngine } from './engine';
import { finite, validateMeasurement } from './schema';
/** Synchronous deterministic replay with hard sample/time/event bounds; no timer storm. */
export function replayMeasurements(engine: InteractionEngine, input: Iterable<Measurement>, options: ReplayOptions = {}): ReplayResult {
  const maxSamples = options.maxSamples ?? 1000;
  const maxDurationMs = options.maxDurationMs ?? 60_000;
  const maxEvents = options.maxEvents ?? 10_000;
  for (const [name, value] of Object.entries({ maxSamples, maxDurationMs, maxEvents })) {
    finite(value, name);
    if (value < 0 || (name !== 'maxDurationMs' && !Number.isInteger(value))) throw new TypeError(`${name} must be a nonnegative budget`);
  }
  if (maxSamples > 100_000 || maxEvents > 100_000 || maxDurationMs > 86_400_000) throw new RangeError('replay budget exceeds SDK hard limit');
  if (options.reset !== false) engine.reset();
  const events: ISIEvent[] = []; let samples = 0; let first: number | undefined;
  for (const inputMeasurement of input) {
    if (samples >= maxSamples || events.length >= maxEvents) return { samples, events, truncated: true };
    const m = validateMeasurement(inputMeasurement);
    first ??= m.timestamp;
    if (Math.abs(m.timestamp - first) > maxDurationMs) return { samples, events, truncated: true };
    const replayed: Measurement = { ...m, source: 'recorded', metadata: { ...m.metadata, replay: true, originalSource: m.metadata?.originalSource ?? m.source } };
    const batch = engine.ingest(replayed); samples++;
    const remaining = maxEvents - events.length;
    events.push(...batch.slice(0, remaining));
    if (batch.length > remaining) return { samples, events, truncated: true };
  }
  return { samples, events, truncated: false };
}
