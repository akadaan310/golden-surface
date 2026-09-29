# Protocol

Relay: `http://40.64.120.87:8490` (on this machine, `http://127.0.0.1:8490`). Tokens: `relay/.env`.
Every endpoint except `/health` needs a seat token, passed as JSON `token`, `?token=`, or `Authorization: Bearer`.

## ر / ن → relay

```bash
. relay/.env; T=$GOLDEN_TOKEN_R; R=http://127.0.0.1:8490
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"newtab\"}"                         # -> {ok, tab}
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"open\",\"tab\":\"t…\",\"url\":\"https://…\"}"
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"read\",\"tab\":\"t…\"}"             # -> data {url,title,text}
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"shot\",\"tab\":\"t…\"}"             # -> data {png: base64}
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"tap\",\"tab\":\"t…\",\"x\":100,\"y\":200}"
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"type\",\"tab\":\"t…\",\"text\":\"hello\"}"   # refused on password fields
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"closetab\",\"tab\":\"t…\"}"
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"login_request\",\"site\":\"Gmail\",\"url\":\"https://mail.google.com/\",\"tab\":\"t…\"}"
curl -s $R/suggested -d "{\"token\":\"$T\",\"service\":\"proton\",\"signupUrl\":\"https://account.proton.me/signup\",\"why\":\"shared mail\"}"
curl -s $R/bus/event -d "{\"token\":\"$T\",\"kind\":\"turn.saved\",\"payload\":{\"round\":1,\"speaker\":\"r\",\"text\":\"…\"}}"
curl -s -H "Authorization: Bearer $T" $R/state      # {tabs:[{id,owner,url,title,signedIn}], activeTabId, phoneRev, twinRev, link}
curl -s -H "Authorization: Bearer $T" $R/sessions   # session map
curl -s -H "Authorization: Bearer $T" $R/sync       # sync report + divergence classes
curl -s -N "$R/bus/stream?token=$T&since=0"         # SSE; kinds=a,b to filter; Last-Event-ID honoured
curl -s -H "Authorization: Bearer $T" "$R/events?since=0&kinds=session.dead"   # ledger query
```

`/cmd` answers:

| Status | Meaning |
|---|---|
| 200 | The phone answered, ok. |
| 422 | The phone refused; the reason is in `error`. |
| 403 | Ownership violation. |
| 404 | No such tab. |
| 503 | Phone offline (non-mutating commands). |
| 202 `{queued:true}` | Phone offline; the mutating op is held in the twin and delivered on reconnect. |

Test hooks: `cmd: desync` drops one op to demonstrate divergence. `cmd: resync {mode: replay|adopt-phone}`.

Conference kinds on the bus: `round.opened {round, topic}`, `turn.saved {round, speaker, text}`,
`chair.direction {text}`, `scribe.note {text}`, `round.closed {round, summary?}`.

## Websocket `/ws?token=APP` (app ⇄ relay)

| Direction | Message |
|---|---|
| app → | `hello {state}` · `ack {rev, id?, rejected?, data?, state}` · `nack {ack}` · `result {id, ok, data?, error?}` · `login_done {site, tab, url, approved, cookies?, owner}` · `probe_result {id, status, reason, finalUrl}` · `suggested_opened {service}` · `signal {kind: session.signed_out|login.custom_tab, …}` |
| ← relay | `welcome {twinRev, base, sessions, suggested, sync}` · `op {rev, op, params, id?}` · `cmd {id, cmd, params}` · `rebase {base}` · `login_request {id, site, url, tab, by, reason}` · `probe {id, url}` · `sessions {sessions}` · `suggested {suggested}` · `sync {status, classes, detail}` · `resync {twinRev}` |

The app also POSTs `/state {state}` on every change (debounced 250 ms).
State shape and sync rules: [SYNC.md](SYNC.md).
