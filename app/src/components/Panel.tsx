import { useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { config, saveConfig } from '../config';
import { cookieBridge } from '../cookies';
import { engine } from '../engine';
import { connect, disconnect, suggestedOpened } from '../relay';
import { blankTab, setUi, updateBrowser, useApp } from '../state';
import { C, SERIF } from '../theme';
import { SEAT_NAME } from '../types';

/** Suggested accounts, the session map, and settings. */
export function Panel({ onClose }: { onClose: () => void }) {
  const suggested = useApp((s) => s.suggested);
  const sessions = useApp((s) => s.sessions);
  const sync = useApp((s) => s.sync);
  const link = useApp((s) => s.link);
  const browser = useApp((s) => s.browser);
  const [url, setUrl] = useState(config().relayUrl);
  const [token, setToken] = useState(config().token);

  const openSignup = (service: string, signupUrl: string) => {
    const t = blankTab('abed', signupUrl);
    updateBrowser((b) => {
      b.tabs.push(t);
      b.activeTabId = t.id;
    });
    suggestedOpened(service);
    setUi({ surface: 'browser' });
    onClose();
  };

  return (
    <Modal animationType="slide" onRequestClose={onClose} transparent={false}>
      <View style={s.wrap}>
        <View style={s.head}>
          <Text style={s.title}>Golden Surface</Text>
          <Pressable onPress={onClose} hitSlop={10}>
            <Text style={s.close}>Close</Text>
          </Pressable>
        </View>
        <ScrollView contentContainerStyle={{ padding: 16 }}>
          <Text style={s.h}>SUGGESTED</Text>
          {suggested.filter((x) => x.status !== 'done').length === 0 ? (
            <Text style={s.muted}>Nothing suggested.</Text>
          ) : null}
          {suggested
            .filter((x) => x.status !== 'done')
            .map((x) => (
              <View key={x.service} style={s.card}>
                <Text style={s.cardTitle}>{x.service}</Text>
                {x.why ? <Text style={s.cardWhy}>{x.why}</Text> : null}
                <Text style={s.faint}>suggested by {SEAT_NAME[x.added_by] ?? x.added_by}{x.status === 'opened' ? ' · opened' : ''}</Text>
                <Pressable style={s.btn} onPress={() => openSignup(x.service, x.signup_url)}>
                  <Text style={s.btnText}>open signup</Text>
                </Pressable>
              </View>
            ))}

          <Text style={s.h}>SESSIONS</Text>
          {sessions.length === 0 ? <Text style={s.muted}>No shared sessions yet.</Text> : null}
          {sessions.map((x) => (
            <View key={x.session_id} style={s.sess}>
              <View style={{ flex: 1 }}>
                <Text style={s.sessSite}>
                  {x.site} <Text style={s.faint}>· {SEAT_NAME[x.owner]}</Text>
                </Text>
                <Text style={s.faint}>
                  {x.check_via === 'phone' ? 'mirror-only: the phone drives, the twin mirrors state' : 'shared into the twin'}
                  {x.check_failures ? ` · ${x.check_failures} failed checks` : ''}
                </Text>
              </View>
              <Text style={[s.status, { color: x.status === 'alive' ? C.green : x.status === 'dead' ? C.red : C.amber }]}>
                {x.status}
              </Text>
            </View>
          ))}

          <Text style={s.h}>SYNC</Text>
          <Text style={s.muted}>
            link {link} · twin sync {sync.status}
            {sync.classes.length ? ` (${sync.classes.join(', ')})` : ''} · phone rev {browser.rev} · acked twin rev{' '}
            {browser.ackTwinRev}
          </Text>

          <Text style={s.h}>RELAY</Text>
          <TextInput style={s.input} value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false}
            placeholder="https://relay…" placeholderTextColor={C.faint} />
          <TextInput style={s.input} value={token} onChangeText={setToken} autoCapitalize="none" autoCorrect={false}
            secureTextEntry placeholder="app token" placeholderTextColor={C.faint} />
          <Pressable
            style={s.btn}
            onPress={async () => {
              await saveConfig({ relayUrl: url, token });
              disconnect();
              connect();
            }}
          >
            <Text style={s.btnText}>save & reconnect</Text>
          </Pressable>
          <Text style={[s.faint, { marginTop: 16 }]}>
            engine: {engine.name} · cookie bridge: {cookieBridge.available ? 'present' : 'absent (Expo Go) — sessions are mirror-only'}
          </Text>
        </ScrollView>
      </View>
    </Modal>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.bg, paddingTop: 36 },
  head: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: 16, paddingBottom: 10 },
  title: { color: C.gold, fontFamily: SERIF, fontSize: 18, letterSpacing: 2 },
  close: { color: C.muted },
  h: { color: C.gold, fontSize: 11, letterSpacing: 3, marginTop: 22, marginBottom: 8 },
  muted: { color: C.muted, fontSize: 13 },
  faint: { color: C.faint, fontSize: 11, marginTop: 2 },
  card: { backgroundColor: C.panel, borderRadius: 8, padding: 12, marginBottom: 10 },
  cardTitle: { color: C.text, fontSize: 16, fontFamily: SERIF },
  cardWhy: { color: C.muted, fontSize: 13, marginTop: 4 },
  btn: { alignSelf: 'flex-start', borderWidth: 1, borderColor: C.gold, borderRadius: 5, paddingHorizontal: 12, paddingVertical: 6, marginTop: 10 },
  btnText: { color: C.gold, fontSize: 12, fontWeight: '600' },
  sess: { flexDirection: 'row', alignItems: 'center', paddingVertical: 8, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: C.line },
  sessSite: { color: C.text, fontSize: 14 },
  status: { fontSize: 12, fontWeight: '700', marginLeft: 8 },
  input: { color: C.text, backgroundColor: C.panel, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 8, marginBottom: 8 },
});
