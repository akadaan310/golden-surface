import type { Measurement, Zone, ZoneMembership } from './types';
/** Boundary distance is negative inside. Uncertainty is a conservative sigma-scaled norm. */
export function evaluateZone(m: Measurement, zone: Zone, sigma = 2): ZoneMembership {
  const unavailable: ZoneMembership = { quality: 'unobservable', inside: false, confidence: 0 };
  if (m.coordinateFrame !== zone.frame || m.relative?.kind === 'rssi') return unavailable;
  let signedDistance: number;
  if (zone.measurement) {
    if (!m.relative || m.relative.kind !== zone.measurement.kind || m.position) return unavailable;
    signedDistance = Math.max(zone.measurement.min - m.relative.value, m.relative.value - zone.measurement.max);
  } else {
    if (!m.position || !zone.center || zone.radius === undefined) return unavailable;
    signedDistance = Math.hypot(...m.position.map((v, i) => v - zone.center![i])) - zone.radius;
  }
  const margin = sigma * Math.hypot(...(m.uncertainty ?? [0]));
  const quality = signedDistance + margin < 0 ? 'inside' : signedDistance - margin > 0 ? 'outside' : 'uncertain';
  return { quality, inside: quality === 'inside', confidence: m.confidence, signedDistance };
}
