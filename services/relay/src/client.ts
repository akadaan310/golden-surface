import { validateEvent, type ISIEvent } from '@golden-motion/isi';

export type RelayState = 'stopped' | 'connecting' | 'authenticating' | 'connected' | 'reconnecting';
export interface RelayEnvelope { type: 'event'; event: ISIEvent; sequence: number; receivedAt: number }
export interface ClientSocket {
  readyState: number;
  bufferedAmount: number;
  onopen: ((event: any) => void) | null;
  onclose: ((event: any) => void) | null;
  onerror: ((event: any) => void) | null;
  onmessage: ((message: any) => void) | null;
  send(data: string): void;
  close(code?: number, reason?: string): void;
}
export interface RelayClientOptions {
  url: string;
  token: string;
  role: 'publisher' | 'subscriber';
  onState?: (state: RelayState) => void;
  onError?: (error: { code: string; message: string }) => void;
  onEvent?: (envelope: RelayEnvelope) => void;
  socketFactory?: (url: string) => ClientSocket;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
}

export class RelayClient {
  private socket?: ClientSocket;
  private retryTimer?: ReturnType<typeof setTimeout>;
  private authTimer?: ReturnType<typeof setTimeout>;
  private running = false;
  private connected = false;
  private retries = 0;
  private lastSequence = 0;

  constructor(private readonly options: RelayClientOptions) {
    // React Native 0.76's built-in URL class lacks protocol/hostname getters.
    // A strict literal endpoint needs no URL parser or DNS resolution.
    const match = /^ws:\/\/127\.0\.0\.1:([0-9]{1,5})\/?$/.exec(options.url);
    if (!match || Number(match[1]) < 1 || Number(match[1]) > 65535) {
      throw new Error('Relay URL must be ws://127.0.0.1:<port> with no credentials, query or path');
    }
    if (typeof options.token !== 'string' || options.token.length < 16 || options.token.length > 256) throw new Error('Invalid local pairing token');
    if (options.role !== 'publisher' && options.role !== 'subscriber') throw new Error('Invalid relay role');
  }

  start(): void {
    if (this.running) return;
    this.running = true;
    this.retries = 0;
    this.connect();
  }

  stop(): void {
    this.running = false;
    this.connected = false;
    if (this.retryTimer !== undefined) clearTimeout(this.retryTimer);
    if (this.authTimer !== undefined) clearTimeout(this.authTimer);
    this.retryTimer = undefined;
    this.authTimer = undefined;
    const socket = this.socket;
    this.socket = undefined;
    if (socket) {
      // An in-flight failed upgrade can still produce an error in Node/RN.
      socket.onopen = null;
      socket.onmessage = null;
      socket.onclose = null;
      socket.onerror = () => {};
      socket.close(1000, 'Stopped');
    }
    this.options.onState?.('stopped');
  }

  publish(event: unknown): boolean {
    if (!this.running || !this.connected || this.options.role !== 'publisher' || !this.socket) return false;
    let packet: string;
    try { packet = JSON.stringify({ type: 'event', event: validateEvent(event) }); }
    catch { this.options.onError?.({ code: 'INVALID_EVENT', message: 'Event does not satisfy the ISI schema' }); return false; }
    const bytes = utf8Bytes(packet);
    if (bytes > 32 * 1024 || this.socket.bufferedAmount + bytes > 64 * 1024) {
      this.options.onError?.({ code: 'BACKPRESSURE', message: 'Publisher output limit reached' });
      return false;
    }
    try { this.socket.send(packet); return true; }
    catch { return false; }
  }

  private connect(): void {
    if (!this.running) return;
    this.options.onState?.('connecting');
    let socket: ClientSocket;
    try {
      socket = this.options.socketFactory ? this.options.socketFactory(this.options.url) : new WebSocket(this.options.url) as unknown as ClientSocket;
    } catch {
      this.options.onError?.({ code: 'CONNECT_FAILED', message: 'Could not open the local relay' });
      this.scheduleReconnect();
      return;
    }
    this.socket = socket;
    this.connected = false;
    this.lastSequence = 0;
    socket.onopen = () => {
      if (!this.running || this.socket !== socket) return;
      this.options.onState?.('authenticating');
      socket.send(JSON.stringify({ type: 'auth', token: this.options.token, role: this.options.role }));
      this.authTimer = setTimeout(() => {
        if (this.socket !== socket || this.connected) return;
        this.options.onError?.({ code: 'AUTH_TIMEOUT', message: 'Local relay authentication timed out' });
        socket.close(1008, 'Authentication timed out');
      }, 5000);
    };
    socket.onmessage = ({ data }) => {
      if (!this.running || this.socket !== socket) return;
      let value: any;
      try { value = JSON.parse(String(data)); }
      catch { this.options.onError?.({ code: 'INVALID_RESPONSE', message: 'Invalid relay response' }); return; }
      if (value?.type === 'error' && typeof value.code === 'string') {
        this.options.onError?.({ code: value.code, message: typeof value.message === 'string' ? value.message : 'Relay rejected a message' });
        if (['AUTH_FAILED', 'AUTH_REQUIRED', 'ROLE_REQUIRED'].includes(value.code)) this.stop();
        return;
      }
      if (!this.connected) {
        if (value?.type !== 'auth' || value.ok !== true || value.role !== this.options.role || value.protocol !== 1) return;
        if (this.authTimer !== undefined) clearTimeout(this.authTimer);
        this.connected = true;
        this.retries = 0;
        this.options.onState?.('connected');
        return;
      }
      if (this.options.role !== 'subscriber' || value?.type !== 'event') return;
      try {
        const event = validateEvent(value.event);
        if (!Number.isSafeInteger(value.sequence) || value.sequence <= this.lastSequence || !Number.isFinite(value.receivedAt)) throw new Error('Invalid sequence');
        this.lastSequence = value.sequence;
        this.options.onEvent?.({ type: 'event', event, sequence: value.sequence, receivedAt: value.receivedAt });
      } catch { this.options.onError?.({ code: 'INVALID_EVENT', message: 'Invalid relay event or sequence' }); }
    };
    socket.onerror = () => {
      if (this.running && this.socket === socket) this.options.onError?.({ code: 'CONNECT_FAILED', message: 'Local relay connection failed' });
    };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      if (this.authTimer !== undefined) clearTimeout(this.authTimer);
      this.socket = undefined;
      this.connected = false;
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (!this.running) return;
    this.options.onState?.('reconnecting');
    const base = Math.max(10, this.options.reconnectBaseMs ?? 250);
    const cap = Math.max(base, this.options.reconnectMaxMs ?? 5000);
    const delay = Math.min(cap, base * 2 ** Math.min(this.retries++, 10));
    this.retryTimer = setTimeout(() => this.connect(), delay);
  }
}

// Hermes and older browser engines need no TextEncoder or Node Buffer dependency.
function utf8Bytes(value: string): number {
  let bytes = 0;
  for (const character of value) {
    const point = character.codePointAt(0)!;
    bytes += point <= 0x7f ? 1 : point <= 0x7ff ? 2 : point <= 0xffff ? 3 : 4;
  }
  return bytes;
}
