# Sync model — phone ⇄ twin

Declared in code at `relay/twin.py` (relay side) and `app/src/commands.ts`
(phone side). This file is the same statement in prose.

## Replicas

| Replica | Where | Holds |
|---|---|---|
| **P** — phone | Abed's Android, the Golden Surface app | The real WebViews. Truth for what is displayed. |
| **T** — twin | The relay on this machine (`TwinModel`) | Same tab model and state shape. ر/ن drive it via `/cmd`. |

State shape (both sides):

```json
{ "rev": 12, "ackTwinRev": 7, "activeTabId": "t1a2b3c4",
  "tabs": [{ "id": "t1a2b3c4", "owner": "r", "url": "https://…", "title": "…", "signedIn": true }] }
```

**Synced (structural) fields:** tab ids, owners, URLs, active tab.
**Observed fields:** title, signedIn, loading. These come from the phone and are never compared.

## Rules

1. **Twin → phone (ops).** Every twin mutation (`newtab`, `open`, `closetab`)
   is an op with a monotonic `twin_rev`. The relay sends ops in rev order.
2. **In-order, idempotent apply.** P applies op `r` only if
   `r == ackTwinRev + 1`. If `r <= ackTwinRev`, the op is a duplicate and is ignored.
   A gap (`r > ackTwinRev + 1`) is answered with `nack {ack}`, and the relay
   resends every pending op. Delivery is at-least-once; application is exactly-once.
3. **Ack means processed.** P acks each op, applied or rejected. A rejection
   (the tab is gone, or the scheme isn't supported) is reported with its reason and
   recorded as a `sync.conflict` event.
4. **Phone → twin (state).** Every phone-side change bumps `phone_rev` and
   POSTs the full state (`POST /state`). T adopts P's state, drops ops P
   has acked, and re-applies ops still pending.
5. **Rebase.** Ops at or below `base` are settled. `base` is the first pending
   rev minus 1, or `twin_rev` if nothing is pending. On `hello`, the relay
   sends `welcome {base}`. A phone whose ack is below `base` fast-forwards to it.
   This covers a relay restart (pending ops are in memory and are lost with the process; this is declared) and a fresh phone install.

## Convergence

```
converged  ⇔  link up  ∧  no pending ops  ∧  hash(structural(T)) == hash(structural(P))
```

Under rules 1–4, with the link up, every op is eventually acked, and T adopts
P after each change. So P and T converge within one round trip once
input stops. `tests/test_relay.py` shows it for normal ops, a dropped op
(then replay), and an op queued while the phone is offline (then redelivered on
reconnect).

## Divergence classes

These are every way P and T can disagree. `classify()` in `relay/twin.py` computes them;
the **sync-convergence** watcher checks every 5 s.

| Class | Meaning | How it ends |
|---|---|---|
| `link-down` | Relay⇄phone websocket down more than 30 s. Neither side can verify the other. | Reconnect. `hello` carries full state, and pending ops are redelivered. |
| `op-in-flight` | An op was sent but not acked within 10 s. | The ack arrives, or Resync (replay). |
| `op-lost` | An op never reached the phone, with the link up. | The next op triggers a nack and resend, or Resync (replay). |
| `op-rejected` | The phone refused an op. | Reported at the moment it happens (`sync.conflict`, and HTTP 422 to the caller). The replicas agree again once T adopts P. |
| `state-mismatch` | No pending ops, but the hashes differ. | Resync. “Keep this phone's tabs” makes T adopt P. |
| `session-mirror-only` | The site is signed in on the phone, but its session isn't in the twin. This happens with VM-challenged sites (Google etc.) or with Expo Go, which can't export cookies. | Not a sync failure: the phone stays the driver for that site. Shown per site in the session list. |

## Surfacing — never silent

- When the watcher sees a transition, it appends `sync.diverged {classes, revs, hashes}` or
  `sync.converged`, and updates `sync_state` (`divergences`, `last_converged_at`, `phone_rev`, `twin_rev`).
- The relay pushes these events to the app. The app shows a red **OUT OF SYNC WITH THE TWIN** banner, which lists
  the classes and offers **Resync (replay twin)** and **Keep this phone's tabs**.
- The app shows its own red **RELAY LINK DOWN** banner the moment the socket drops, with elapsed time and tap-to-retry.
- `GET /sync` exposes the live report: revs, pending ops with ages, both hashes, and classes.

## Breaking sync on purpose (acceptance 7)

```bash
. relay/.env
# drop one op on the floor: twin applies it, phone never hears it
curl -s localhost:8490/cmd -d "{\"token\":\"$GOLDEN_TOKEN_R\",\"cmd\":\"desync\"}"
# within ~5 s: sync.diverged {classes:[op-lost]} → red banner on the phone
curl -s -H "Authorization: Bearer $GOLDEN_TOKEN_R" localhost:8490/sync | python3 -m json.tool
```

Tap **Resync** on the phone, or send the next `/cmd` (the phone nacks the gap and the relay resends).
Then `sync.converged` arrives and the banner clears.
