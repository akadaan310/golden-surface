import type { CalibrationTransform, Measurement, Vec3 } from './types';
import { clone, finite, isMetricFrame, nonempty, validateMeasurement } from './schema';
export function validateCalibration(transform: CalibrationTransform): CalibrationTransform {
  nonempty(transform.id, 'calibration.id'); nonempty(transform.fromFrame, 'fromFrame'); nonempty(transform.toFrame, 'toFrame');
  if (!isMetricFrame(transform.fromFrame) || !isMetricFrame(transform.toFrame)) throw new TypeError('calibration needs explicit metric spatial frames');
  const r = transform.rotation;
  if (!Array.isArray(r) || r.length !== 9 || !Array.isArray(transform.translation) || transform.translation.length !== 3) throw new TypeError('calibration requires a 3x3 rotation and Vec3 translation');
  [...r, ...transform.translation].forEach(v => finite(v, 'calibration component'));
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
    let dot = 0; for (let k = 0; k < 3; k++) dot += r[i * 3 + k] * r[j * 3 + k];
    if (Math.abs(dot - (i === j ? 1 : 0)) > 1e-6) throw new TypeError('calibration rotation must be orthogonal without scaling');
  }
  const determinant = r[0] * (r[4] * r[8] - r[5] * r[7]) - r[1] * (r[3] * r[8] - r[5] * r[6]) + r[2] * (r[3] * r[7] - r[4] * r[6]);
  if (Math.abs(determinant - 1) > 1e-6) throw new TypeError('calibration rotation must preserve handedness');
  return clone(transform);
}
/** Applies an explicit rigid transform. It cannot reconstruct a scalar or image measurement. */
export function applyCalibration(input: Measurement, transform: CalibrationTransform): Measurement {
  const m = validateMeasurement(input); const t = validateCalibration(transform);
  if (!m.position || m.coordinateFrame !== t.fromFrame) throw new TypeError('calibration requires a spatial observation in its source frame');
  const rotate = (v: Vec3): Vec3 => [0,1,2].map(i => t.rotation[i * 3] * v[0] + t.rotation[i * 3 + 1] * v[1] + t.rotation[i * 3 + 2] * v[2]) as Vec3;
  const position = rotate(m.position).map((v, i) => v + t.translation[i]) as Vec3;
  const uncertainty = m.uncertainty ? [0,1,2].map(i => Math.sqrt(m.uncertainty!.reduce((sum, s, j) => sum + (t.rotation[i * 3 + j] * s) ** 2, 0))) : undefined;
  return { ...m, position, coordinateFrame: t.toFrame, calibrationId: t.id,
    ...(m.velocity ? { velocity: rotate(m.velocity) } : {}), ...(uncertainty ? { uncertainty } : {}),
    metadata: { ...m.metadata, calibration: { id: t.id, fromFrame: t.fromFrame, toFrame: t.toFrame, uncertaintyModel: 'independent input axes; marginal output standard deviations' } } };
}
export class CalibrationRegistry {
  private transforms = new Map<string, CalibrationTransform>();
  register(transform: CalibrationTransform): void {
    const value = validateCalibration(transform);
    if (!this.transforms.has(value.id) && this.transforms.size >= 256) throw new RangeError('calibration registry capacity exceeded');
    this.transforms.set(value.id, value);
  }
  remove(id: string): boolean { return this.transforms.delete(id); }
  apply(measurement: Measurement, id: string): Measurement {
    const transform = this.transforms.get(id);
    if (!transform) throw new Error(`unknown calibration ${id}`);
    return applyCalibration(measurement, transform);
  }
}
