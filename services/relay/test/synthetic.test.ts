import { expect, it } from 'vitest';
import WebSocket from 'ws';
import { startRelay } from '../src/server';
import { runSyntheticPublisher } from '../src/synthetic-publisher';

it('the native-shaped command publishes bounded synthetic evidence, never physical phone evidence', async () => {
  const token = 'synthetic-demo-test-local-token-32';
  const relay = await startRelay({ token, port: 0 });
  const subscriber = new WebSocket(relay.address);
  const events: any[] = [];
  try {
    await new Promise<void>((resolve, reject) => {
      subscriber.once('open', resolve);
      subscriber.once('error', reject);
    });
    const authenticated = new Promise<void>((resolve) => subscriber.once('message', () => resolve()));
    subscriber.send(JSON.stringify({ type: 'auth', token, role: 'subscriber' }));
    await authenticated;
    subscriber.on('message', (data) => events.push(JSON.parse(String(data))));
    expect(await runSyntheticPublisher({ url: relay.address, token, count: 3, intervalMs: 20 })).toEqual({ published: 3 });
    expect(events).toHaveLength(3);
    expect(events.every((envelope) => envelope.event.source === 'synthetic')).toBe(true);
    expect(events.every((envelope) => envelope.event.metadata.evidence === 'synthetic-native-shaped-protocol-demo')).toBe(true);
    expect(events.map((envelope) => envelope.sequence)).toEqual([1, 2, 3]);
    expect(events[0].event.deviceId).toBe('synthetic-native-shaped-device');
  } finally {
    subscriber.terminate();
    await relay.close();
  }
});

it('publishes synthetic CSI-derived motion presence with measurement units and no position', async () => {
  const token = 'synthetic-rf-demo-test-local-token-32';
  const relay = await startRelay({ token, port: 0 });
  const subscriber = new WebSocket(relay.address);
  const events: any[] = [];
  try {
    await new Promise<void>((resolve, reject) => {
      subscriber.once('open', resolve);
      subscriber.once('error', reject);
    });
    const authenticated = new Promise<void>((resolve) => subscriber.once('message', () => resolve()));
    subscriber.send(JSON.stringify({ type: 'auth', token, role: 'subscriber' }));
    await authenticated;
    subscriber.on('message', (data) => events.push(JSON.parse(String(data))));
    await runSyntheticPublisher({ url: relay.address, token, count: 2, intervalMs: 20, modality: 'wifi-csi' });
    expect(events).toHaveLength(2);
    expect(events[0].event).toMatchObject({ type: 'motion-presence', source: 'synthetic', modality: 'wifi-csi', coordinateFrame: 'measurement-space',
      relative: { kind: 'motion-score', unit: 'unitless' } });
    expect(events[0].event.position).toBeUndefined();
  } finally {
    subscriber.terminate();
    await relay.close();
  }
});

it('cleans up reconnect attempts when the command fails to pair with an unavailable relay', async () => {
  const token = 'unavailable-demo-test-local-token-32';
  const relay = await startRelay({ token, port: 0 });
  const address = relay.address;
  const port = Number(new URL(address).port);
  await relay.close();
  await expect(runSyntheticPublisher({ url: address, token, count: 1, intervalMs: 20 })).rejects.toThrow();
  const restarted = await startRelay({ token, port });
  try {
    await new Promise((resolve) => setTimeout(resolve, 350));
    expect(restarted.stats().connections).toBe(0);
  } finally { await restarted.close(); }
});
