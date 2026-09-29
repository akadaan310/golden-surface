# Acceptance — how each item is checked

| # | Item | How | Status |
|---|---|---|---|
| 1 | Store from schema.sql; session map | `python3 store/test_store.py`; `python3 store/store.py map` | machine-verified |
| 2 | Relay unit; /cmd, /state, /sessions | `systemctl status golden-relay`; `python3 tests/test_relay.py` (FakePhone) | machine-verified |
| 3 | Bus streams; events persisted | `tests/test_relay.py` (bus section) | machine-verified |
| 4 | Watchers as units; kill a session → alert | `systemctl list-units 'golden-*'`; `python3 tests/test_watchers.py` | machine-verified |
| 5 | Expo Go: ر opens tab → banner → Abed signs in to Google → ر reads | Needs Abed's phone: Expo Go → `exp://40.64.120.87:8491`. Then run the steps below. | see BUILDLOG |
| 6 | Kill app, reopen: tabs/URLs/sessions persist | On the phone, or the emulator run in BUILDLOG | see BUILDLOG |
| 7 | Sync model declared; break sync → loud | [SYNC.md](SYNC.md); `cmd: desync` → red banner | see BUILDLOG |
| 8 | APK builds, installs, launches | `app/android/app/build/outputs/apk/debug/app-debug.apk`; emulator install and launch | see BUILDLOG |

## Item 5 on the phone

```bash
. relay/.env; T=$GOLDEN_TOKEN_R; R=http://127.0.0.1:8490
TAB=$(curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"newtab\"}" | python3 -c 'import sys,json;print(json.load(sys.stdin)["tab"])')
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"login_request\",\"site\":\"Gmail\",\"url\":\"https://mail.google.com/\",\"tab\":\"$TAB\"}"
# phone: gold banner "ر needs this signed in — your fingers only." → Sign in → Abed types his password → "Done · share with the counsel"
curl -s -H "Authorization: Bearer $T" $R/sessions        # Gmail, owner r, alive, approved_by_abed_at set, check_via phone
curl -s $R/cmd -d "{\"token\":\"$T\",\"cmd\":\"read\",\"tab\":\"$TAB\"}" | head -c 600
```
