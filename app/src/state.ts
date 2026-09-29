import AsyncStorage from '@react-native-async-storage/async-storage';
import { useSyncExternalStore } from 'react';
import type {
  BrowserState, LoginRequest, Notice, Owner, SessionRow, Suggested, SyncStatus, Tab,
} from './types';
import { aiOf } from './ai';
import { withLocked } from './locked';
import { siteOf } from './routing';

/** One store for the app. Browser state persists to AsyncStorage on every
 *  change (tabs + URLs restore on relaunch); cookies/localStorage persist in
 *  the WebView profile itself. Every browser change is also posted to the relay. */

export interface AppState {
  browser: BrowserState;
  hydrated: boolean;
  link: 'connecting' | 'up' | 'down';
  linkSince: number;
  sessions: SessionRow[];
  suggested: Suggested[];
  logins: LoginRequest[];
  sync: SyncStatus;
  notices: Notice[];
  surface: 'browser' | 'najwa';
}

const KEY = 'gs.browser.v1';
const listeners = new Set<() => void>();
const changeHooks = new Set<(b: BrowserState) => void>();

const newId = () => 'p' + Math.random().toString(36).slice(2, 10);
export const nowIso = () => new Date().toISOString();

export function blankTab(owner: Owner, url = 'about:blank', id = newId()): Tab {
  return { id, owner, url, title: '', signedIn: false, createdAt: nowIso(), src: { uri: url, n: 0 } };
}

const lockedTab = (d: { id: string; owner: Owner; home: string }) => blankTab(d.owner, d.home, d.id);

let state: AppState = {
  browser: { rev: 0, ackTwinRev: 0, tabs: [], activeTabId: null },
  hydrated: false,
  link: 'connecting',
  linkSince: Date.now(),
  sessions: [],
  suggested: [],
  logins: [],
  sync: { status: 'unknown', classes: [] },
  notices: [],
  surface: 'browser',
};

export const getState = () => state;

function emit() {
  listeners.forEach((l) => l());
}

export function setUi(patch: Partial<Omit<AppState, 'browser'>>) {
  state = { ...state, ...patch };
  emit();
}

/** Mutate browser state. Every call is a phone-side change: rev bumps, it is
 *  persisted, and the relay is told (see relay.ts). */
export function updateBrowser(fn: (b: BrowserState) => BrowserState | void, opts: { silent?: boolean } = {}) {
  const draft: BrowserState = JSON.parse(JSON.stringify(state.browser));
  const out = fn(draft) ?? draft;
  out.tabs = withLocked(out.tabs, lockedTab).map((t) => ({ ...t, signedIn: isSignedIn(t.url), ai: aiOf(t.url) }));
  if (!out.tabs.some((t) => t.id === out.activeTabId)) out.activeTabId = out.tabs[0].id;
  if (!opts.silent) out.rev = state.browser.rev + 1;
  state = { ...state, browser: out };
  emit();
  persist();
  if (!opts.silent) changeHooks.forEach((h) => h(out));
}

export const onBrowserChange = (h: (b: BrowserState) => void) => {
  changeHooks.add(h);
  return () => changeHooks.delete(h);
};

let persistTimer: ReturnType<typeof setTimeout> | null = null;
function persist() {
  if (persistTimer) clearTimeout(persistTimer);
  persistTimer = setTimeout(() => {
    AsyncStorage.setItem(KEY, JSON.stringify(state.browser)).catch((e) =>
      notify('error', `Could not save tabs: ${String(e)}`),
    );
  }, 150);
}

export async function hydrate() {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (raw) {
      const b: BrowserState = JSON.parse(raw);
      // restore: every tab reloads its last committed URL
      b.tabs = b.tabs.map((t) => ({ ...t, src: { uri: t.url || t.src.uri, n: 0 }, loading: false, crashed: false }));
      state = { ...state, browser: b };
    }
  } catch (e) {
    notify('error', `Saved tabs could not be restored: ${String(e)}`);
  }
  if (!state.browser.tabs.length) {
    const t = blankTab('abed', 'https://www.google.com/');
    state = { ...state, browser: { ...state.browser, tabs: [t], activeTabId: t.id } };
  }
  // the locked tabs are there on every launch, whatever was saved
  const tabs = withLocked(state.browser.tabs, lockedTab).map((t) => ({ ...t, ai: aiOf(t.url) }));
  state = { ...state, browser: { ...state.browser, tabs } };
  state = { ...state, hydrated: true };
  emit();
}

export function isSignedIn(url: string) {
  const host = siteOf(url);
  if (!host) return false;
  return state.sessions.some(
    (s) => (s.status === 'alive' || s.status === 'expiring') &&
      (host === s.site_id || host.endsWith('.' + s.site_id) || s.site_id.endsWith('.' + host)),
  );
}

export function setSessions(sessions: SessionRow[]) {
  state = { ...state, sessions };
  updateBrowser(() => {}, { silent: false });
}

export function notify(level: Notice['level'], text: string, action?: Notice['action']) {
  const id = Math.random().toString(36).slice(2);
  // de-duplicate identical notices
  const notices = state.notices.filter((n) => n.text !== text);
  setUi({ notices: [...notices, { id, level, text, action }] });
  if (level === 'info') setTimeout(() => dismiss(id), 6000);
  return id;
}

export const dismiss = (id: string) => setUi({ notices: state.notices.filter((n) => n.id !== id) });

export function useApp<T>(sel: (s: AppState) => T): T {
  return useSyncExternalStore(
    (l) => {
      listeners.add(l);
      return () => listeners.delete(l);
    },
    () => sel(state),
  );
}

export const tabById = (id: string | null | undefined) => state.browser.tabs.find((t) => t.id === id);
