import { afterEach, describe, expect, it, vi } from 'vitest';
import WebSocket from 'ws';
import { startRelay, type RelayServer } from '../src/server';
import { RelayClient, type RelayState } from '../src/client';

const token = 'portable-client-pairing-token-long-enough';
const clients: RelayClient[] = [];
const servers: RelayServer[] = [];
async function server(port = 0) {
  const relay = await startRelay({ token, port });
  servers.push(relay);
  return relay;
}
const factory = (url: string) => new WebSocket(url);

function until(predicate: () => boolean, timeout = 2000): Promise<void> {
  return new Promise((resolve, reject) => {
    const began = Date.now();
    const check = () => {
      if (predicate()) return resolve();
      if (Date.now() - began > timeout) return reject(new Error('Client state did not arrive'));
      setTimeout(check, 10);
    };
    check();
  });
}

afterEach(async () => {
  clients.splice(0).forEach((client) => client.stop());
  await Promise.all(servers.splice(0).map((relay) => relay.close()));
});

describe('portable authenticated client lifecycle', () => {
  it('pairs on React Native without relying on its incomplete URL getters', () => {
    // RN 0.76 Libraries/Blob/URL.js throws from protocol/hostname getters.
    vi.stubGlobal('URL', class { get protocol(): string { throw new Error('URL.protocol is not implemented'); } });
    try {
      expect(() => new RelayClient({ url: 'ws://127.0.0.1:8787', token, role: 'publisher' })).not.toThrow();
    } finally { vi.unstubAllGlobals(); }
  });

  it('rejects URLs that could expose the pairing token outside IPv4 loopback', () => {
    for (const url of ['ws://192.168.0.2:8787', 'wss://example.com', 'ws://127.0.0.1:8787/?token=secret', 'ws://127.0.0.1:0', 'ws://127.0.0.1:99999']) {
      expect(() => new RelayClient({ url, token, role: 'subscriber', socketFactory: factory })).toThrow();
    }
  });

  it('authenticates before connected and explicitly stops its socket', async () => {
    const states: RelayState[] = [];
    const relay = await server();
    const client = new RelayClient({ url: relay.address, token, role: 'subscriber', socketFactory: factory, onState: (state) => states.push(state) });
    clients.push(client);
    client.start();
    await until(() => states.includes('connected'));
    expect(states.slice(0, 3)).toEqual(['connecting', 'authenticating', 'connected']);
    client.stop();
    expect(states.at(-1)).toBe('stopped');
  });

  it('stops automatic retries when authentication fails', async () => {
    const states: RelayState[] = [];
    const errors: string[] = [];
    const relay = await server();
    const client = new RelayClient({ url: relay.address, token: 'wrong-token-otherwise-long', role: 'subscriber', socketFactory: factory,
      reconnectBaseMs: 10, reconnectMaxMs: 30, onState: (state) => states.push(state), onError: (error) => errors.push(error.code) });
    clients.push(client);
    client.start();
    await until(() => states.at(-1) === 'stopped');
    expect(errors).toContain('AUTH_FAILED');
    expect(states).not.toContain('reconnecting');
  });

  it('reconnects and reauthenticates after the local relay is restarted', async () => {
    const states: RelayState[] = [];
    const first = await server();
    const client = new RelayClient({ url: first.address, token, role: 'subscriber', socketFactory: factory,
      reconnectBaseMs: 10, reconnectMaxMs: 30, onState: (state) => states.push(state) });
    clients.push(client);
    client.start();
    await until(() => states.includes('connected'));
    const port = Number(new URL(first.address).port);
    await first.close();
    servers.splice(servers.indexOf(first), 1);
    await until(() => states.includes('reconnecting'));
    await server(port);
    await until(() => states.filter((state) => state === 'connected').length === 2);
    client.stop();
    const count = states.length;
    await new Promise((resolve) => setTimeout(resolve, 80));
    expect(states.length).toBe(count);
  });
});
