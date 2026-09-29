import * as WebBrowser from 'expo-web-browser';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { loginDone, signal } from '../relay';
import { siteOf } from '../routing';
import { blankTab, getState, notify, setUi, tabById, updateBrowser, useApp } from '../state';
import { C } from '../theme';
import { ltr, SEAT_NAME, type LoginRequest } from '../types';

/** The login handoff. The relay sends login_request {site, url, tab}; Abed
 *  signs in with his own fingers; the app reports login_done {site, tab}.
 *  Nothing here ever reads or fills a password. */
export function LoginBanners() {
  const logins = useApp((s) => s.logins);
  return (
    <>
      {logins.map((l) => (
        <LoginBanner key={l.id} req={l} />
      ))}
    </>
  );
}

const update = (id: string, patch: Partial<LoginRequest>) =>
  setUi({ logins: getState().logins.map((l) => (l.id === id ? { ...l, ...patch } : l)) });
const drop = (id: string) => setUi({ logins: getState().logins.filter((l) => l.id !== id) });

function start(req: LoginRequest) {
  let tabId = req.tab && tabById(req.tab) ? req.tab : null;
  updateBrowser((b) => {
    if (!tabId) {
      const t = blankTab(req.by, req.url);
      b.tabs.push(t);
      tabId = t.id;
    } else {
      const t = b.tabs.find((x) => x.id === tabId)!;
      if (req.url && siteOf(t.url) !== siteOf(req.url)) {
        t.src = { uri: req.url, n: t.src.n + 1 };
        t.url = req.url;
      }
    }
    b.activeTabId = tabId;
  });
  setUi({ surface: 'browser' });
  update(req.id, { stage: 'signing-in', tabId: tabId! });
}

/** Fallback when Google blocks the embedded sign-in: a Chrome Custom Tab.
 *  If the flow returns to goldensurface://sso?url=..., that URL loads back in
 *  the tab. Otherwise the session stayed in Chrome — said out loud, not hidden. */
export async function openInChrome(url: string, tabId: string) {
  try {
    const res = await WebBrowser.openAuthSessionAsync(url, 'goldensurface://sso');
    const back = res.type === 'success' && res.url ? new URL(res.url).searchParams.get('url') : null;
    if (back) {
      updateBrowser((b) => {
        const t = b.tabs.find((x) => x.id === tabId);
        if (t) {
          t.src = { uri: back, n: t.src.n + 1 };
          t.url = back;
        }
      });
      signal('login.custom_tab', { site: siteOf(url), tab: tabId, broughtBack: true });
    } else {
      signal('login.custom_tab', { site: siteOf(url), tab: tabId, broughtBack: false });
      notify('error', `Signed in through Chrome: that session lives in Chrome, not in the Surface. ` +
        `For ${siteOf(url)} the phone stays the driver.`);
    }
  } catch (e) {
    notify('error', `Chrome sign-in failed: ${String(e)}`);
  }
}

function LoginBanner({ req }: { req: LoginRequest }) {
  const who = SEAT_NAME[req.by] ?? 'ر';
  if (req.stage === 'asked') {
    return (
      <View style={s.box}>
        <Text style={s.head}>{ltr(`${who} needs this signed in — your fingers only.`)}</Text>
        <Text style={s.sub}>
          {req.site}
          {req.reason ? ` · ${req.reason}` : ''}
        </Text>
        <View style={s.row}>
          <Btn label="Sign in" primary onPress={() => start(req)} />
          <Btn label="Not now" onPress={() => drop(req.id)} />
        </View>
      </View>
    );
  }
  const tabId = req.tabId!;
  return (
    <View style={s.box}>
      <Text style={s.head}>Signing in to {req.site}</Text>
      <Text style={s.sub}>Type your password yourself. When you're in:</Text>
      <View style={s.row}>
        <Btn
          label="Done · share with the counsel"
          primary
          onPress={() => {
            loginDone(req.site, tabId, true);
            drop(req.id);
          }}
        />
        <Btn
          label="Done · keep private"
          onPress={() => {
            loginDone(req.site, tabId, false);
            drop(req.id);
          }}
        />
      </View>
      <View style={s.row}>
        <Btn label="Google blocked it? Use Chrome" onPress={() => openInChrome(tabById(tabId)?.url || req.url, tabId)} />
        <Btn label="Cancel" onPress={() => drop(req.id)} />
      </View>
    </View>
  );
}

function Btn({ label, onPress, primary }: { label: string; onPress: () => void; primary?: boolean }) {
  return (
    <Pressable onPress={onPress} style={[s.btn, primary && s.btnPrimary]}>
      <Text style={[s.btnText, primary && { color: C.bg }]}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  box: { backgroundColor: '#2a2208', borderLeftWidth: 3, borderColor: C.gold, padding: 12 },
  head: { color: C.gold, fontSize: 15, fontWeight: '600' },
  sub: { color: C.text, fontSize: 13, marginTop: 3 },
  row: { flexDirection: 'row', flexWrap: 'wrap', marginTop: 8 },
  btn: { borderWidth: 1, borderColor: C.gold, borderRadius: 5, paddingHorizontal: 10, paddingVertical: 6, marginRight: 8, marginTop: 4 },
  btnPrimary: { backgroundColor: C.gold },
  btnText: { color: C.gold, fontSize: 12, fontWeight: '600' },
});
