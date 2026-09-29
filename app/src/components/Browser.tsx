import { useCallback, useEffect, useState } from 'react';
import { Alert, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { askUrl, type TabContext } from '../ai';
import { engine, handleFor, registerHandle, type EngineEvent } from '../engine';
import { isLocked, lockedDef } from '../locked';
import { loginDone, signal } from '../relay';
import { looksLikeLogin, normalizeInput, route, siteOf } from '../routing';
import { blankTab, notify, tabById, updateBrowser, useApp } from '../state';
import { C } from '../theme';
import { ltr, SEAT_COLOR, SEAT_NAME, type Tab } from '../types';
import { openInChrome } from './LoginBanner';

export function navigate(tabId: string, url: string) {
  const r = route(url);
  if (r.kind !== 'web') {
    notify('warn', r.message);
    return;
  }
  updateBrowser((b) => {
    const t = b.tabs.find((x) => x.id === tabId);
    if (t) {
      t.src = { uri: url, n: t.src.n + 1 };
      t.url = url;
    }
  });
}

export function newTab(url = 'about:blank') {
  const t = blankTab('abed', url);
  updateBrowser((b) => {
    b.tabs.push(t);
    b.activeTabId = t.id;
  });
  return t.id;
}

export function closeTab(id: string) {
  if (isLocked(id)) {
    notify('info', 'Locked tabs stay open. ⌂ takes one back home.');
    return;
  }
  updateBrowser((b) => {
    const i = b.tabs.findIndex((t) => t.id === id);
    b.tabs = b.tabs.filter((t) => t.id !== id);
    if (b.activeTabId === id) b.activeTabId = b.tabs.length ? b.tabs[Math.max(0, i - 1)].id : null;
  });
}

const onEngineEvent = (tabId: string, ev: EngineEvent) => {
  const tab = tabById(tabId);
  if (!tab) return;
  switch (ev.type) {
    case 'nav': {
      const wasSignedIn = tab.signedIn;
      const wasAi = tab.ai;
      if (tab.url === ev.url && tab.title === ev.title && !!tab.loading === ev.loading) return;
      updateBrowser((b) => {
        const t = b.tabs.find((x) => x.id === tabId);
        if (t) Object.assign(t, { url: ev.url, title: ev.title, loading: ev.loading, crashed: false });
      });
      // the browser knows when an LLM is engaged: say so to the relay once per entry
      const nowAi = tabById(tabId)?.ai;
      if (nowAi && nowAi !== wasAi) signal('llm.engaged', { ai: nowAi, tab: tabId, url: ev.url });
      // a site we hold a session for just showed its login wall: say so, loudly
      if (!ev.loading && wasSignedIn && looksLikeLogin(ev.url)) {
        const site = siteOf(ev.url);
        notify('error', `Signed out of ${site}? This tab landed on its login page.`);
        signal('session.signed_out', { site, url: ev.url, tab: tabId });
      }
      return;
    }
    case 'crash':
      updateBrowser((b) => {
        const t = b.tabs.find((x) => x.id === tabId);
        if (t) t.crashed = true;
      });
      notify('error', `A tab's page died (${ev.reason}). It will reload when you open it.`);
      return;
    case 'scheme':
      notify('warn', ev.message);
      return;
    case 'google-blocked':
      notify('error', 'Google refused sign-in inside the Surface.', {
        label: 'Sign in via Chrome',
        run: () => openInChrome(ev.url, tabId),
      });
      return;
    case 'http-error':
      notify('warn', `${siteOf(ev.url)} answered HTTP ${ev.status}.`);
      return;
  }
};

export function Browser() {
  const browser = useApp((s) => s.browser);
  const active = browser.tabs.find((t) => t.id === browser.activeTabId) ?? null;
  const register = useCallback(registerHandle, []);
  const [crashKeys, setCrashKeys] = useState<Record<string, number>>({});

  // a crashed tab is remounted when it becomes active
  useEffect(() => {
    if (active?.crashed) {
      setCrashKeys((k) => ({ ...k, [active.id]: (k[active.id] ?? 0) + 1 }));
      updateBrowser((b) => {
        const t = b.tabs.find((x) => x.id === active.id);
        if (t) {
          t.crashed = false;
          t.src = { uri: t.url, n: 0 };
        }
      });
    }
  }, [active?.id, active?.crashed]);

  return (
    <View style={s.wrap}>
      <TabStrip tabs={browser.tabs} activeId={browser.activeTabId} />
      {active ? <AddressBar tab={active} /> : null}
      {active && active.owner !== 'abed' ? (
        <View style={[s.ownerBar, { borderColor: SEAT_COLOR[active.owner] }]}>
          <Text style={[s.ownerText, { color: SEAT_COLOR[active.owner] }]}>
            {ltr(`${SEAT_NAME[active.owner]}'s tab — driven through the relay`)}
          </Text>
        </View>
      ) : null}
      <View style={[s.stage, active && { borderTopColor: SEAT_COLOR[active.owner] }]}>
        {browser.tabs.map((t) => (
          <engine.TabView
            key={t.id + ':' + (crashKeys[t.id] ?? 0)}
            tab={t}
            visible={t.id === browser.activeTabId}
            onEvent={onEngineEvent}
            register={register}
          />
        ))}
        {!browser.tabs.length ? (
          <View style={s.empty}>
            <Text style={s.emptyText}>No tabs. Tap + to open one.</Text>
          </View>
        ) : null}
      </View>
    </View>
  );
}

function TabStrip({ tabs, activeId }: { tabs: Tab[]; activeId: string | null }) {
  return (
    <View style={s.strip}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ alignItems: 'center' }}>
        {tabs.map((t) => {
          const on = t.id === activeId;
          return (
            <Pressable
              key={t.id}
              onPress={() => updateBrowser((b) => void (b.activeTabId = t.id))}
              style={[s.chip, on && s.chipOn, { borderTopColor: SEAT_COLOR[t.owner] }]}
            >
              <Text style={[s.badge, { color: SEAT_COLOR[t.owner] }]}>{SEAT_NAME[t.owner]}</Text>
              {t.signedIn ? <View style={s.signed} /> : null}
              <Text numberOfLines={1} style={[s.chipText, on && { color: C.text }]}>
                {t.crashed ? '⚠ ' : ''}{t.locked ? lockedDef(t.id)?.label : t.title || siteOf(t.url) || 'New tab'}
              </Text>
              {t.ai ? <Text style={s.ai}>✦</Text> : null}
              {t.locked ? (
                <Text style={s.lock}>🔒</Text>
              ) : (
                <Pressable hitSlop={8} onPress={() => closeTab(t.id)}>
                  <Text style={s.x}>×</Text>
                </Pressable>
              )}
            </Pressable>
          );
        })}
      </ScrollView>
      <Pressable style={s.plus} onPress={() => newTab()} hitSlop={6}>
        <Text style={s.plusText}>+</Text>
      </Pressable>
    </View>
  );
}

const CONTEXT_JS = `return {title: document.title,
  text: (document.body ? document.body.innerText : '').slice(0, 4000)};`;

/** ?question in any address bar: ask an unsigned Google AI Mode with this tab's
 *  context carried in the URL. A tab on a shared session gives only its address
 *  and title. An AI tab gives no page context of its own. */
export async function askWithTab(tab: Tab, question: string) {
  if (!question.trim()) return;
  let ctx: TabContext | null = null;
  if (!tab.ai && tab.url && tab.url !== 'about:blank') {
    ctx = { url: tab.url, title: tab.title };
    if (!tab.signedIn) {
      try {
        const r = await handleFor(tab.id)?.evaluate<{ title: string; text: string }>(CONTEXT_JS, 3000);
        if (r) ctx = { ...ctx, title: r.title || ctx.title, text: r.text };
      } catch {
        // page text unavailable: ask with the address and title only
      }
    }
  }
  newTab(askUrl(question, ctx));
  signal('llm.asked', { ai: 'google-ai-mode', fromTab: tab.id, withText: !!ctx?.text });
}

function AddressBar({ tab }: { tab: Tab }) {
  const [text, setText] = useState(tab.url);
  const [editing, setEditing] = useState(false);
  useEffect(() => {
    if (!editing) setText(tab.url === 'about:blank' ? '' : tab.url);
  }, [tab.url, tab.id, editing]);
  const site = siteOf(tab.url);
  const sessions = useApp((st) => st.sessions);
  const shared = sessions.some((x) => x.site_id === site && x.approved_by_abed_at);

  const share = () =>
    Alert.alert(
      `Share ${site}?`,
      `Your ${site} session in the Surface becomes the counsel's: ر and ن can use it. Your password stays on this phone.`,
      [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Share', onPress: () => loginDone(site, tab.id, true) },
      ],
    );

  return (
    <View style={s.bar}>
      <Pressable hitSlop={6} onPress={() => handleFor(tab.id)?.goBack()}>
        <Text style={s.navBtn}>‹</Text>
      </Pressable>
      <TextInput
        style={s.url}
        value={text}
        onChangeText={setText}
        onFocus={() => setEditing(true)}
        onBlur={() => setEditing(false)}
        onSubmitEditing={() => {
          setEditing(false);
          if (text.trim().startsWith('?')) askWithTab(tab, text.trim().slice(1));
          else navigate(tab.id, normalizeInput(text));
        }}
        placeholder="Search, address, or ?ask about this tab"
        placeholderTextColor={C.faint}
        autoCapitalize="none"
        autoCorrect={false}
        keyboardType="url"
        returnKeyType="go"
        selectTextOnFocus
      />
      {tab.locked ? (
        <Pressable hitSlop={6} onPress={() => navigate(tab.id, lockedDef(tab.id)!.home)}>
          <Text style={s.navBtn}>⌂</Text>
        </Pressable>
      ) : null}
      <Pressable hitSlop={6} onPress={() => handleFor(tab.id)?.reload()}>
        <Text style={s.navBtn}>{tab.loading ? '·' : '↻'}</Text>
      </Pressable>
      {site && !shared ? (
        <Pressable hitSlop={6} onPress={share}>
          <Text style={s.share}>share</Text>
        </Pressable>
      ) : null}
    </View>
  );
}

const s = StyleSheet.create({
  wrap: { flex: 1, backgroundColor: C.bg },
  strip: { flexDirection: 'row', alignItems: 'center', backgroundColor: C.panel, paddingLeft: 6, height: 44 },
  chip: {
    flexDirection: 'row', alignItems: 'center', maxWidth: 170, paddingHorizontal: 10, height: 34,
    marginRight: 4, borderRadius: 6, borderTopWidth: 2, backgroundColor: C.bg, opacity: 0.7,
  },
  chipOn: { backgroundColor: C.raised, opacity: 1 },
  badge: { fontWeight: '700', marginRight: 6, fontSize: 13 },
  signed: { width: 5, height: 5, borderRadius: 3, backgroundColor: C.green, marginRight: 5 },
  chipText: { color: C.muted, fontSize: 12, flexShrink: 1 },
  x: { color: C.faint, fontSize: 16, marginLeft: 8 },
  lock: { color: C.faint, fontSize: 12, marginLeft: 8 },
  ai: { color: C.gold, fontSize: 11, marginLeft: 6 },
  plus: { width: 40, alignItems: 'center' },
  plusText: { color: C.gold, fontSize: 22 },
  bar: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 6, backgroundColor: C.raised },
  navBtn: { color: C.muted, fontSize: 20, paddingHorizontal: 8 },
  url: { flex: 1, color: C.text, backgroundColor: C.bg, borderRadius: 6, paddingHorizontal: 10, paddingVertical: 6, fontSize: 13 },
  share: { color: C.gold, fontSize: 12, paddingHorizontal: 6 },
  ownerBar: { paddingVertical: 3, paddingHorizontal: 12, backgroundColor: C.panel, borderLeftWidth: 3 },
  ownerText: { fontSize: 11, letterSpacing: 0.5 },
  stage: { flex: 1, borderTopWidth: 2, borderTopColor: C.line },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  emptyText: { color: C.faint },
});
