import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { reconnectNow, resync } from '../relay';
import { dismiss, getState, setUi, useApp } from '../state';
import { C } from '../theme';

/** Everything that can go wrong is said here, loudly. Nothing fails silently. */

const CLASS_TEXT: Record<string, string> = {
  'link-down': 'relay link is down — the twin cannot see this phone',
  'op-in-flight': 'a remote command has not been confirmed by this phone',
  'op-lost': 'a remote command never arrived here',
  'op-rejected': 'this phone refused a remote command',
  'state-mismatch': 'the twin and this phone disagree about the tabs',
  'session-mirror-only': 'a session lives only on this phone',
};

export function LinkBanner() {
  const link = useApp((s) => s.link);
  const since = useApp((s) => s.linkSince);
  const [, tick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(t);
  }, []);
  const secs = Math.round((Date.now() - since) / 1000);
  if (link === 'up' || (link === 'connecting' && secs < 5)) return null;
  return (
    <Pressable onPress={reconnectNow} style={[s.bar, s.red]}>
      <Text style={s.redHead}>RELAY LINK DOWN · {fmt(secs)}</Text>
      <Text style={s.body}>
        ر and ن can't reach this browser, and changes here aren't reaching the twin. Retrying — tap to retry now.
      </Text>
    </Pressable>
  );
}

export function SyncBanner() {
  const sync = useApp((s) => s.sync);
  const link = useApp((s) => s.link);
  if (sync.status !== 'diverged' || link !== 'up') return null;
  return (
    <View style={[s.bar, s.red]}>
      <Text style={s.redHead}>OUT OF SYNC WITH THE TWIN</Text>
      {sync.classes.map((c) => (
        <Text key={c} style={s.body}>
          • {CLASS_TEXT[c] ?? c}
        </Text>
      ))}
      <View style={s.row}>
        <Pressable style={s.btn} onPress={() => resync('replay')}>
          <Text style={s.btnText}>Resync (replay twin)</Text>
        </Pressable>
        <Pressable style={s.btn} onPress={() => resync('adopt-phone')}>
          <Text style={s.btnText}>Keep this phone's tabs</Text>
        </Pressable>
      </View>
    </View>
  );
}

export function SessionBanner() {
  const sessions = useApp((s) => s.sessions);
  const logins = useApp((s) => s.logins);
  const bad = sessions.filter(
    (x) => x.approved_by_abed_at && (x.status === 'dead' || x.status === 'expiring') &&
      !logins.some((l) => l.site === x.site),
  );
  if (!bad.length) return null;
  return (
    <View style={[s.bar, bad.some((b) => b.status === 'dead') ? s.red : s.amber]}>
      {bad.map((b) => (
        <View key={b.session_id} style={s.sessRow}>
          <Text style={[s.body, { flex: 1 }]}>
            <Text style={{ fontWeight: '700' }}>{b.site}</Text> session is {b.status}
            {b.status === 'dead' ? ' — sign in again' : ''}
          </Text>
          <Pressable
            style={s.btn}
            onPress={() =>
              setUi({
                logins: [...getState().logins, {
                  id: 'local-' + b.session_id, site: b.site, url: b.base_url, tab: null, by: b.owner === 'abed' ? 'r' : b.owner,
                  reason: `session ${b.status}`, stage: 'asked',
                }],
              })
            }
          >
            <Text style={s.btnText}>Sign in</Text>
          </Pressable>
        </View>
      ))}
    </View>
  );
}

export function Notices() {
  const notices = useApp((s) => s.notices);
  return (
    <>
      {notices.map((n) => (
        <View key={n.id} style={[s.bar, n.level === 'error' ? s.red : n.level === 'warn' ? s.amber : s.info]}>
          <View style={s.sessRow}>
            <Text style={[s.body, { flex: 1 }]}>{n.text}</Text>
            {n.action ? (
              <Pressable
                style={s.btn}
                onPress={() => {
                  n.action!.run();
                  dismiss(n.id);
                }}
              >
                <Text style={s.btnText}>{n.action.label}</Text>
              </Pressable>
            ) : null}
            <Pressable hitSlop={10} onPress={() => dismiss(n.id)}>
              <Text style={s.close}>×</Text>
            </Pressable>
          </View>
        </View>
      ))}
    </>
  );
}

const fmt = (s: number) => (s < 60 ? `${s}s` : s < 3600 ? `${Math.floor(s / 60)}m` : `${Math.floor(s / 3600)}h`);

const s = StyleSheet.create({
  bar: { paddingHorizontal: 12, paddingVertical: 8, borderLeftWidth: 3 },
  red: { backgroundColor: C.redBg, borderColor: C.red },
  amber: { backgroundColor: C.amberBg, borderColor: C.amber },
  info: { backgroundColor: C.raised, borderColor: C.faint },
  redHead: { color: C.red, fontWeight: '800', letterSpacing: 1, fontSize: 13 },
  body: { color: C.text, fontSize: 12, marginTop: 2 },
  row: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 6 },
  sessRow: { flexDirection: 'row', alignItems: 'center' },
  btn: { borderWidth: 1, borderColor: C.text, borderRadius: 5, paddingHorizontal: 8, paddingVertical: 4, marginRight: 8, marginTop: 2 },
  btnText: { color: C.text, fontSize: 11, fontWeight: '600' },
  close: { color: C.muted, fontSize: 18, paddingLeft: 10 },
});
