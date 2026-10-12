import WebSocket from 'ws';
import type { ISIEvent } from '@golden-motion/isi';
import { RelayClient } from './client';

/** Protocol fixture only: does not acquire phone sensors or ESP32 hardware. */
export async function runSyntheticPublisher(options: { url: string; token: string; count?: number; intervalMs?: number; modality?: 'native' | 'wifi-csi' }): Promise<{ published: number }> {
  const count = options.count ?? 60;
  const intervalMs = options.intervalMs ?? 50;
  if (!Number.isSafeInteger(count) || count < 1 || count > 2000 || !Number.isSafeInteger(intervalMs) || intervalMs < 20 || intervalMs > 1000) {
    throw new Error('Synthetic demo requires 1–2000 events at 20–1000 ms intervals');
  }
  let failed: Error | undefined;
  let resolvePairing!: () => void;
  let rejectPairing!: (error: Error) => void;
  const pairing = new Promise<void>((resolve, reject) => {
    resolvePairing = resolve;
    rejectPairing = reject;
  });
  const client = new RelayClient({ ...options, role: 'publisher', socketFactory: (url) => new WebSocket(url),
    onState: (state) => { if (state === 'connected') resolvePairing(); },
    onError: (error) => { failed = new Error(`Relay rejected synthetic demo: ${error.code}`); rejectPairing(failed); },
  });
  const timeout = setTimeout(() => rejectPairing(new Error('Local relay pairing timed out')), 5000);
  let published = 0;
  try {
    client.start();
    await pairing;
    clearTimeout(timeout);
    for (let i = 0; i < count; i++) {
      if (failed) throw failed;
      const rf = options.modality === 'wifi-csi';
      const value = Math.sin(i * 0.15);
      const event: ISIEvent = {
        id: `synthetic-demo-${Date.now()}-${i}`,
        type: rf ? 'motion-presence' : 'hover',
        timestamp: Date.now(), source: 'synthetic',
        modality: rf ? 'wifi-csi' : 'native-shaped-fixture',
        deviceId: rf ? 'synthetic-esp32-shaped-device' : 'synthetic-native-shaped-device',
        coordinateFrame: rf ? 'measurement-space' : 'phone-local-m',
        confidence: 0.8,
        ...(rf ? { relative: { kind: 'motion-score', value: 0.5 + 0.3 * value, unit: 'unitless' }, uncertainty: [0.1] }
          : { position: [0.04 * value, 0, 0.12] as [number, number, number], uncertainty: [0.01, 0.01, 0.02] }),
        metadata: { evidence: rf ? 'synthetic-esp32-csi-derived-protocol-demo' : 'synthetic-native-shaped-protocol-demo', physicalAcquisition: false },
      };
      if (!client.publish(event)) throw new Error('Synthetic publisher lost its authenticated connection');
      published++;
      await new Promise<void>((resolve) => setTimeout(resolve, intervalMs));
    }
    return { published };
  } finally { clearTimeout(timeout); client.stop(); }
}
