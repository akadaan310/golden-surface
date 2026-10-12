import { afterEach, describe, expect, it } from 'vitest';
import WebSocket from 'ws';
import { startRelay, type RelayServer } from '../src/server';
import type { ISIEvent } from '@golden-motion/isi';

const token = 'test-local-pairing-token-32-characters';
const servers: RelayServer[] = [];
const clients: WebSocket[] = [];
let eventSerial = 0;
function event(overrides: Partial<ISIEvent> = {}): ISIEvent {
  return { id: `event-${++eventSerial}`, type: 'hover', timestamp: Date.now(), source: 'synthetic',
    modality: 'native-shaped-fixture', deviceId: 'synthetic-galaxy-a16', coordinateFrame: 'phone-local-m',
    confidence: 0.8, position: [0, 0, 0.1], ...overrides };
}
function publish(socket: WebSocket, value: ISIEvent) {
  socket.send(JSON.stringify({ type: 'event', event: value }));
}

async function relay(options: Record<string, unknown> = {}) {
  const server = await startRelay({ token, port: 0, ...options });
  servers.push(server);
  return server;
}

async function connect(url: string) {
  const socket = new WebSocket(url);
  clients.push(socket);
  await new Promise<void>((resolve, reject) => {
    socket.once('open', resolve);
    socket.once('error', reject);
  });
  return socket;
}

function message(socket: WebSocket): Promise<any> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Expected relay response')), 1500);
    socket.once('message', (data) => {
      clearTimeout(timer);
      resolve(JSON.parse(String(data)));
    });
  });
}

async function authenticate(socket: WebSocket, role = 'subscriber', pairingToken = token) {
  const result = message(socket);
  socket.send(JSON.stringify({ type: 'auth', token: pairingToken, role }));
  return result;
}

afterEach(async () => {
  clients.splice(0).forEach((socket) => socket.terminate());
  await Promise.all(servers.splice(0).map((server) => server.close()));
});

describe('authenticated loopback transport', () => {
  it('binds only IPv4 loopback and authenticates an explicit subscriber role', async () => {
    const server = await relay();
    expect(server.address).toMatch(/^ws:\/\/127\.0\.0\.1:/);
    const socket = await connect(server.address);
    expect(await authenticate(socket)).toEqual({ type: 'auth', ok: true, role: 'subscriber', protocol: 1 });
  });

  it('rejects events before authentication and never exposes a pairing token in errors', async () => {
    const server = await relay();
    const socket = await connect(server.address);
    const response = message(socket);
    socket.send(JSON.stringify({ type: 'event', event: {} }));
    const result = await response;
    expect(result.code).toBe('AUTH_REQUIRED');
    expect(JSON.stringify(result)).not.toContain(token);
  });

  it('rejects wrong tokens and unsupported roles', async () => {
    const server = await relay();
    expect((await authenticate(await connect(server.address), 'subscriber', 'wrong-token')).code).toBe('AUTH_FAILED');
    expect((await authenticate(await connect(server.address), 'administrator')).code).toBe('AUTH_FAILED');
  });

  it('rejects event writes from authenticated subscribers', async () => {
    const socket = await connect((await relay()).address);
    await authenticate(socket);
    const response = message(socket);
    socket.send(JSON.stringify({ type: 'event', event: {} }));
    expect((await response).code).toBe('ROLE_REQUIRED');
  });

  it('closes a publisher that sends malformed JSON', async () => {
    const socket = await connect((await relay()).address);
    await authenticate(socket, 'publisher');
    const response = message(socket);
    socket.send('not-json');
    expect((await response).code).toBe('INVALID_JSON');
  });

  it('uses SDK validation to reject missing and nonfinite event fields', async () => {
    const socket = await connect((await relay()).address);
    await authenticate(socket, 'publisher');
    const response = message(socket);
    socket.send(JSON.stringify({ type: 'event', event: { timestamp: null, confidence: 9 } }));
    expect((await response).code).toBe('INVALID_EVENT');
  });

  it('enforces the 32 KiB WebSocket payload cap', async () => {
    const socket = await connect((await relay()).address);
    await authenticate(socket, 'publisher');
    const closed = new Promise<number>((resolve) => socket.once('close', resolve));
    socket.send('x'.repeat(32 * 1024 + 1));
    expect(await closed).toBe(1009);
  });

  it('broadcasts the unchanged validated event with sequence and host receive time', async () => {
    const server = await relay();
    const publisher = await connect(server.address);
    const subscriber = await connect(server.address);
    await authenticate(publisher, 'publisher');
    await authenticate(subscriber);
    const value = event();
    const response = message(subscriber);
    publish(publisher, value);
    const received = await response;
    expect(received).toMatchObject({ type: 'event', event: value, sequence: 1 });
    expect(received.receivedAt).toBeGreaterThanOrEqual(value.timestamp);
    expect(received.receivedAt).toBeLessThanOrEqual(Date.now());
  });

  it('accepts derived RF motion presence without inventing a position', async () => {
    const server = await relay();
    const publisher = await connect(server.address);
    const subscriber = await connect(server.address);
    await authenticate(publisher, 'publisher');
    await authenticate(subscriber);
    const value = event({ type: 'motion-presence', modality: 'wifi-csi', coordinateFrame: 'measurement-space', position: undefined,
      relative: { kind: 'motion-score', value: 0.72, unit: 'unitless' }, metadata: { evidence: 'synthetic-esp32-csi-derived-fixture' } });
    const response = message(subscriber);
    publish(publisher, value);
    const received = await response;
    expect(received.event.type).toBe('motion-presence');
    expect(received.event.source).toBe('synthetic');
    expect(received.event.position).toBeUndefined();
  });

  it('rejects duplicates and backward timestamps across publisher reconnects', async () => {
    const server = await relay();
    const publisher = await connect(server.address);
    const subscriber = await connect(server.address);
    await authenticate(publisher, 'publisher');
    await authenticate(subscriber);
    const value = event();
    const received = message(subscriber);
    publish(publisher, value);
    await received;
    const duplicate = message(publisher);
    publish(publisher, value);
    expect((await duplicate).code).toBe('DUPLICATE');
    const backwards = message(publisher);
    publish(publisher, event({ timestamp: value.timestamp - 1 }));
    expect((await backwards).code).toBe('OUT_OF_ORDER');
    publisher.terminate();
    const reconnected = await connect(server.address);
    await authenticate(reconnected, 'publisher');
    const replay = message(reconnected);
    publish(reconnected, value);
    expect((await replay).code).toBe('DUPLICATE');
    const next = message(subscriber);
    publish(reconnected, event({ timestamp: value.timestamp + 1 }));
    expect((await next).sequence).toBe(2);
  });

  it('rejects device timestamps outside the documented host clock window', async () => {
    const socket = await connect((await relay()).address);
    await authenticate(socket, 'publisher');
    for (const timestamp of [Date.now() - 31_000, Date.now() + 6_000]) {
      const response = message(socket);
      publish(socket, event({ timestamp }));
      expect((await response).code).toBe('CLOCK_SKEW');
    }
  });

  it('closes an event storm at the configured bounded message rate', async () => {
    const socket = await connect((await relay({ maxMessagesPerSecond: 4 })).address);
    await authenticate(socket, 'publisher');
    const response = message(socket);
    const closed = new Promise<number>((resolve) => socket.once('close', resolve));
    for (let i = 0; i < 200; i++) publish(socket, event({ id: `storm-${i}` }));
    expect((await response).code).toBe('RATE_LIMIT');
    expect(await closed).toBe(1008);
  });

  it('bounds tracked device metadata per publisher', async () => {
    const socket = await connect((await relay({ maxDevicesPerPublisher: 2 })).address);
    await authenticate(socket, 'publisher');
    publish(socket, event({ deviceId: 'one' }));
    publish(socket, event({ deviceId: 'two' }));
    const response = message(socket);
    publish(socket, event({ deviceId: 'three' }));
    expect((await response).code).toBe('DEVICE_LIMIT');
  });

  it('bounds subscriber output before adding a frame to its send queue', async () => {
    const server = await relay({ maxBufferedBytes: 768 });
    const publisher = await connect(server.address);
    const subscriber = await connect(server.address);
    await authenticate(publisher, 'publisher');
    await authenticate(subscriber);
    const closed = new Promise<number>((resolve) => subscriber.once('close', resolve));
    publish(publisher, event({ metadata: { diagnostic: 'x'.repeat(1000) } }));
    expect(await closed).toBe(1013);
  });

  it('times out connections that never authenticate', async () => {
    const socket = await connect((await relay({ authTimeoutMs: 30 })).address);
    const response = message(socket);
    expect((await response).code).toBe('AUTH_TIMEOUT');
  });

  it('refuses upgrades from nonlocal browser origins', async () => {
    const server = await relay();
    const socket = new WebSocket(server.address, { origin: 'https://attacker.example' });
    clients.push(socket);
    const failure = new Promise<string>((resolve) => socket.once('error', (error) => resolve(error.message)));
    expect(await failure).toContain('403');
  });
});
