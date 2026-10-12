# Local event relay

The relay binds **127.0.0.1:8787**. It forwards validated ISI events from an authenticated local publisher to authenticated subscribers. It carries derived events from native, acoustic, optical and RF adapters; it does not acquire sensors, accept raw CSI streams, or infer extra spatial dimensions.

From the repository root:

```sh
npm run relay
```

Without `GM_RELAY_TOKEN`, startup creates a 256-bit ephemeral token and prints it once. Copy that token into the local web/native pairing controls. The token changes when the process restarts. An explicit `GM_RELAY_TOKEN` must contain 16–256 characters and is never printed by the relay. `GM_RELAY_PORT` changes the local port, not the network interface.

## Protocol v1

Connect to `ws://127.0.0.1:8787/`; send UTF-8 JSON text. No query parameters or URL credentials are supported. The first frame is:

```json
{"type":"auth","token":"<current-local-token>","role":"publisher"}
```

Use `subscriber` for a receiving client. Success returns:

```json
{"type":"auth","ok":true,"role":"publisher","protocol":1}
```

An authenticated publisher sends `{"type":"event","event":<ISIEvent>}`. Every authenticated subscriber receives `{"type":"event","event":<validated ISIEvent>,"sequence":1,"receivedAt":<host epoch ms>}`. Validation uses `@golden-motion/isi.validateEvent`; unknown fields are normalized according to that SDK. The relay preserves declared `source`, `modality`, coordinate frame, uncertainty and metadata. RF `motion-presence` may carry a `measurement-space` scalar without a position. A device label or `source: live` declaration is publisher supplied and is not independent acquisition evidence.

Errors have `{"type":"error","code":"...","message":"..."}`. Authentication, role, malformed input, resource limits and policy errors close with 1008. Oversized WebSocket payloads close with 1009. A slow subscriber closes with 1013 and must reconnect. `DUPLICATE`, `OUT_OF_ORDER` and `CLOCK_SKEW` reject the event but keep an otherwise valid publisher connection open. No publication acknowledgement or history replay is supplied.

## Portable client

The `client` subpath has no Node dependencies and is usable by browsers and React Native:

```ts
import { RelayClient } from '@golden-motion/relay/client';
const client = new RelayClient({
  url: 'ws://127.0.0.1:8787', token, role: 'subscriber',
  onState: state => console.log(state),
  onEvent: envelope => consume(envelope.event),
  onError: error => showLocalStatus(error.code),
});
client.start();
// On component unmount, explicit stop or application background:
client.stop();
```

For a publisher, use `role: 'publisher'` and `client.publish(event)`. It returns `false` when stopped, disconnected, invalid, oversized or above the outbound buffer limit. There is no offline queue: reconnect does not trigger old sensor actions. Connection retry grows from 250 ms to a 5 s maximum. Wrong credentials halt retries. A transport outage loses in-flight events; this is a best-effort live stream. Node-only scripts inject `socketFactory: url => new WebSocket(url)` from `ws`.

## Android USB pairing

Connect an authorized Android device over USB, enable its normal debug bridge connection and run:

```sh
adb devices
adb reverse tcp:8787 tcp:8787
```

Start the host relay and enter its current token in the Android application. Both native and browser clients use `ws://127.0.0.1:8787`. Stop the native session on background/unmount. When finished, remove the mapping with `adb reverse --remove tcp:8787`. A custom port requires the same port on both sides of `adb reverse`. Do not bind to a public interface or configure a network forwarder to the relay.

## Clock, ordering and resource bounds

The device uses epoch milliseconds and must keep its clock within **30 s behind / 5 s ahead** of the host. `receivedAt` is a host receive time; it does not correct clocks or measure one-way latency. Events older than that clock window must be rebased deliberately by a replay adapter, with original acquisition time retained in provenance.

Events for each `deviceId` must have nondecreasing timestamps, including after publisher reconnect. Distinct event IDs at the same timestamp are allowed. The most recent 128 event ID hashes per device reject duplicates; older duplicate identifiers are not a permanent replay defence. Restarting the relay resets sequence numbers and all ordering state. Two publishers using the same device ID share that ordering record; use distinct stable device IDs.

Default bounds: 32 connections, 5 s authentication timeout, 32 KiB payload, 100 input messages/s/connection (authentication counts), 500 accepted events/s globally, 16 devices/publisher, 128 tracked devices, 128 recent ID hashes/device, and 64 KiB pending subscriber/client output. Frame buffers and ordering hashes live only in memory. Full event payloads have no server history and are never written to disk. Device metadata remains bounded until shutdown; reaching the device cap requires removing the stale session by restarting the relay. Idle authenticated sockets use a 15 s ping/pong heartbeat.

Browser upgrade origins must be HTTP(S) on `localhost`, `127.0.0.1` or `[::1]`; native/Node requests may omit Origin. Origin filtering supplements the token, which is required in all cases. The relay does not implement TLS and should be used for local USB pairing only.

## Synthetic protocol demonstrations

Set the token from the running relay in the publisher's environment, then:

```sh
npm run synthetic --workspace @golden-motion/relay
GM_DEMO_MODALITY=wifi-csi npm run synthetic --workspace @golden-motion/relay
```

Default output is 60 events at 20 Hz. `GM_DEMO_COUNT` accepts 1–2000 events. Native-shaped fixtures use `source: synthetic` and `metadata.evidence: synthetic-native-shaped-protocol-demo`; CSI fixtures use `synthetic-esp32-csi-derived-protocol-demo`. Both declare `physicalAcquisition: false`. Neither command communicates with a phone or an ESP32.

```sh
npm test --workspace @golden-motion/relay
npm run typecheck --workspace @golden-motion/relay
```
