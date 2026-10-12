import { createHash, timingSafeEqual } from 'node:crypto';
import type { AddressInfo } from 'node:net';
import type { IncomingMessage } from 'node:http';
import WebSocket, { WebSocketServer } from 'ws';
import { validateEvent } from '@golden-motion/isi';

export interface RelayOptions {
  token: string;
  port?: number;
  authTimeoutMs?: number;
  maxMessagesPerSecond?: number;
  maxEventsPerSecond?: number;
  maxConnections?: number;
  maxDevices?: number;
  maxDevicesPerPublisher?: number;
  maxBufferedBytes?: number;
}

export interface RelayServer {
  address: string;
  stats(): { connections: number; trackedDevices: number; acceptedEvents: number; rejectedMessages: number };
  close(): Promise<void>;
}

type Role = 'publisher' | 'subscriber';
interface DeviceOrder { timestamp: number; hashes: Set<string>; order: string[] }
function positive(value: number | undefined, fallback: number, ceiling: number): number {
  if (value === undefined) return fallback;
  if (!Number.isSafeInteger(value) || value < 1 || value > ceiling) throw new Error('Invalid relay resource limit');
  return value;
}

/** No host option: transport must never bind a public interface. */
export async function startRelay(options: RelayOptions): Promise<RelayServer> {
  if (typeof options.token !== 'string' || options.token.length < 16 || options.token.length > 256) {
    throw new Error('Pairing token must contain 16–256 characters');
  }
  const limits = {
    authTimeoutMs: positive(options.authTimeoutMs, 5000, 30_000),
    maxMessagesPerSecond: positive(options.maxMessagesPerSecond, 100, 5000),
    maxEventsPerSecond: positive(options.maxEventsPerSecond, 500, 10_000),
    maxConnections: positive(options.maxConnections, 32, 128),
    maxDevices: positive(options.maxDevices, 128, 512),
    maxDevicesPerPublisher: positive(options.maxDevicesPerPublisher, 16, 128),
    maxBufferedBytes: positive(options.maxBufferedBytes, 64 * 1024, 256 * 1024),
  };
  const secret = Buffer.from(options.token);
  const server = new WebSocketServer({
    host: '127.0.0.1',
    port: options.port ?? 8787,
    maxPayload: 32 * 1024,
    perMessageDeflate: false,
    verifyClient: ({ origin, req }: { origin: string; req: IncomingMessage }, done: (result: boolean, code?: number) => void) => {
      if (req.socket.remoteAddress !== '127.0.0.1' || req.url !== '/') return done(false, 403);
      if (server.clients.size >= limits.maxConnections) return done(false, 503);
      if (!origin) return done(true); // Native/Node clients have no browser Origin.
      try {
        const parsed = new URL(origin);
        done(['http:', 'https:'].includes(parsed.protocol) && ['127.0.0.1', 'localhost', '[::1]'].includes(parsed.hostname), 403);
      } catch { done(false, 403); }
    },
  });
  const roles = new Map<WebSocket, Role>();
  const devices = new Map<string, DeviceOrder>();
  let sequence = 0;
  let rejectedMessages = 0;
  let globalWindow = Date.now();
  let globalEvents = 0;
  let closing = false;
  server.on('connection', (socket) => {
    socket.on('error', () => { /* Oversized frames and failed peers must not crash the relay. */ });
    const publisherDevices = new Set<string>();
    let windowStart = Date.now();
    let messages = 0;
    let rejected = false;
    let alive = true;
    socket.on('pong', () => { alive = true; });
    const heartbeat = setInterval(() => {
      if (!alive) return socket.terminate();
      alive = false;
      if (socket.readyState === WebSocket.OPEN) socket.ping();
    }, 15_000);
    heartbeat.unref();
    function reject(code: string, message: string, fatal = true) {
      rejectedMessages++;
      if (socket.readyState !== WebSocket.OPEN) return;
      const packet = JSON.stringify({ type: 'error', code, message });
      if (socket.bufferedAmount + Buffer.byteLength(packet) > limits.maxBufferedBytes) {
        rejected = true;
        socket.close(1013, 'Output limit');
        return;
      }
      socket.send(packet);
      if (fatal) {
        rejected = true;
        socket.close(1008, code);
      }
    }
    const authTimeout = setTimeout(() => reject('AUTH_TIMEOUT', 'Pairing timed out'), limits.authTimeoutMs);
    authTimeout.unref();
    socket.on('close', () => {
      roles.delete(socket);
      publisherDevices.clear();
      clearTimeout(authTimeout);
      clearInterval(heartbeat);
    });
    socket.on('message', (data, binary) => {
      if (rejected || closing) return;
      const now = Date.now();
      if (now - windowStart >= 1000) { windowStart = now; messages = 0; }
      if (++messages > limits.maxMessagesPerSecond) return reject('RATE_LIMIT', 'Message rate limit reached');
      if (binary) return reject('TEXT_REQUIRED', 'Use JSON text frames');
      let value: any;
      try { value = JSON.parse(String(data)); }
      catch { return reject('INVALID_JSON', 'Expected JSON'); }
      if (!value || typeof value !== 'object' || Array.isArray(value)) return reject('INVALID_MESSAGE', 'Expected an object');
      if (!roles.has(socket)) {
        if (value.type !== 'auth') return reject('AUTH_REQUIRED', 'Authenticate before publishing or subscribing');
        const candidate = typeof value.token === 'string' ? Buffer.from(value.token) : Buffer.alloc(0);
        if (candidate.length !== secret.length || !timingSafeEqual(candidate, secret) || !['publisher', 'subscriber'].includes(value.role)) {
          return reject('AUTH_FAILED', 'Invalid pairing token or role');
        }
        roles.set(socket, value.role);
        clearTimeout(authTimeout);
        socket.send(JSON.stringify({ type: 'auth', ok: true, role: value.role, protocol: 1 }));
        return;
      }
      if (roles.get(socket) !== 'publisher') return reject('ROLE_REQUIRED', 'Publisher role required');
      if (value.type !== 'event') return reject('INVALID_MESSAGE', 'Expected an event envelope');
      let event;
      try { event = validateEvent(value.event); }
      catch { return reject('INVALID_EVENT', 'Event does not satisfy the ISI schema'); }
      if (event.timestamp < now - 30_000 || event.timestamp > now + 5000) return reject('CLOCK_SKEW', 'Device epoch clock must be within -30/+5 seconds of host', false);
      if (event.id.length > 256 || event.deviceId.length > 256) return reject('INVALID_EVENT', 'Event and device identifiers are limited to 256 characters');
      if (!publisherDevices.has(event.deviceId) && publisherDevices.size >= limits.maxDevicesPerPublisher) return reject('DEVICE_LIMIT', 'Publisher device limit reached');
      if (!devices.has(event.deviceId) && devices.size >= limits.maxDevices) return reject('DEVICE_LIMIT', 'Relay device limit reached');
      const hash = createHash('sha256').update(event.id).digest('hex');
      let ordered = devices.get(event.deviceId);
      if (ordered?.hashes.has(hash)) return reject('DUPLICATE', 'Duplicate event identifier', false);
      if (ordered && event.timestamp < ordered.timestamp) return reject('OUT_OF_ORDER', 'Timestamp precedes latest device event', false);
      if (now - globalWindow >= 1000) { globalWindow = now; globalEvents = 0; }
      if (++globalEvents > limits.maxEventsPerSecond) return reject('RATE_LIMIT', 'Global event rate limit reached');
      if (!ordered) {
        ordered = { timestamp: event.timestamp, hashes: new Set(), order: [] };
        devices.set(event.deviceId, ordered);
      }
      ordered.timestamp = event.timestamp;
      ordered.hashes.add(hash);
      ordered.order.push(hash);
      if (ordered.order.length > 128) ordered.hashes.delete(ordered.order.shift()!);
      publisherDevices.add(event.deviceId);
      const packet = JSON.stringify({ type: 'event', event, sequence: ++sequence, receivedAt: now });
      const bytes = Buffer.byteLength(packet);
      for (const [subscriber, role] of roles) {
        if (role !== 'subscriber' || subscriber.readyState !== WebSocket.OPEN) continue;
        if (subscriber.bufferedAmount + bytes > limits.maxBufferedBytes) subscriber.close(1013, 'Output limit');
        else subscriber.send(packet);
      }
    });
  });
  await new Promise<void>((resolve, reject) => {
    server.once('listening', resolve);
    server.once('error', reject);
  });
  const address = server.address() as AddressInfo;
  return {
    address: `ws://127.0.0.1:${address.port}`,
    stats: () => ({ connections: server.clients.size, trackedDevices: devices.size, acceptedEvents: sequence, rejectedMessages }),
    close: () => new Promise<void>((resolve, reject) => {
      if (closing) return resolve();
      closing = true;
      for (const socket of server.clients) socket.terminate();
      devices.clear();
      roles.clear();
      server.close((error) => error ? reject(error) : resolve());
    }),
  };
}
