export type Vec3 = [number, number, number];
export type MeasurementSource = 'synthetic' | 'recorded' | 'live';
export type ISIEventType = 'hover' | 'approach' | 'retreat' | 'swipe' | 'scroll' | 'hold' | 'select' | 'cancel' | 'drag' | 'rotate' | 'zone-enter' | 'zone-exit' | 'motion-3d' | 'motion-presence';
export type InteractionState = 'idle' | 'hovering' | 'holding' | 'selected' | 'dragging' | 'cancelled';
export interface RelativeMeasurement { kind: string; value: number; unit: string }
export interface Measurement {
  timestamp: number; source: MeasurementSource; modality: string; deviceId: string;
  coordinateFrame: string; confidence: number; position?: Vec3; velocity?: Vec3;
  relative?: RelativeMeasurement; uncertainty?: number[]; calibrationId?: string;
  intent?: boolean; metadata?: Record<string, unknown>;
}
export interface ISIEvent extends Omit<Measurement, 'intent'> {
  id: string; type: ISIEventType; zoneId?: string; interactionState?: InteractionState;
}
export interface Zone {
  id: string; frame: string; center?: Vec3; radius?: number;
  measurement?: { kind: string; min: number; max: number };
}
export interface EngineOptions {
  zones?: Zone[]; minConfidence?: number; dwellMs?: number; cooldownMs?: number;
  hysteresis?: number; dropoutMs?: number; debounceMs?: number; maxAgeMs?: number;
  /** Finite live epoch tolerances; replay/synthetic clocks remain independent by default. */
  liveMaxAgeMs?: number; maxFutureMs?: number;
  now?: () => number; uncertaintySigma?: number; minMotionSpeed?: number;
  swipeSpeed?: number; scrollScale?: number; maxScrollDelta?: number;
}
export type EventListener = (event: ISIEvent) => void;
export interface ZoneMembership {
  quality: 'inside' | 'outside' | 'uncertain' | 'unobservable'; inside: boolean;
  confidence: number; signedDistance?: number;
}
export interface MeasurementAdapter {
  id: string;
  start: (emit: (measurement: Measurement) => void) => void | (() => void) | Promise<void | (() => void)>;
  stop?: () => void | Promise<void>;
}
export interface SubscriptionFilter {
  types?: ISIEventType[]; deviceId?: string; modality?: string; zoneId?: string;
  minConfidence?: number; source?: MeasurementSource;
}
export interface CalibrationTransform {
  id: string; fromFrame: string; toFrame: string;
  /** Row-major proper orthogonal 3x3 matrix; units remain metres. */
  rotation: [number, number, number, number, number, number, number, number, number];
  translation: Vec3;
}
export interface ReplayOptions { maxSamples?: number; maxDurationMs?: number; maxEvents?: number; reset?: boolean }
export interface ReplayResult { samples: number; events: ISIEvent[]; truncated: boolean }
