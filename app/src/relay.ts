import { onCmd, onOp } from './commands';
import { config, wsUrl } from './config';
import { cookieBridge } from './cookies';
import { looksLikeLogin } from './routing';
import {
  getState, notify, onBrowserChange, setSessions, setUi, tabById, updateBrowser,
} from './state';
import type { BrowserState, LoginRequest } from './types';

/** The app's link to the relay.
 *  Reconnect: exponential backoff 1s -> 30s with jitter, reset on success;
 *  also retried immediately when the app returns to the foreground.
 *  Telemetry: full browser state POSTed to /state on every change (debounced
 *  250 ms); if the POST fails the state rides along with the next hello. */

let ws: WebSocket | null = null;
let backoff = 1000;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let stopped = false;

export const send = (m: object) => {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(m));
};

function setLink(link: 'connecting' | 'up' | 'down') {
  if (getState().link !== link) setUi({ link, linkSince: Date.now() });
}

export function connect() {
  stopped = false;
  if (retryTimer) clearTimeout(retryTimer);
  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
  if (!config().token) {
    setLink('down');
    notify('error', 'No relay token set — open Settings.');
    return;
  }
  setLink('connecting');
  const sock = new WebSocket(wsUrl());
  ws = sock;
  sock.onopen = () => {
    backoff = 1000;
    setLink('up');
    sock.send(JSON.stringify({ type: 'hello', state: getState().browser }));
  };
  sock.onmessage = (e) => {
    try {
      handle(JSON.parse(String(e.data)));
    } catch (err) {
      notify('error', `Bad message from relay: ${String(err)}`);
    }
  };
  sock.onerror = () => {};
  sock.onclose = (e) => {
    if (ws === sock) ws = null;
    setLink('down');
    if (e.code === 4000) {
      // another Golden Surface (e.g. Expo Go and the APK on one phone) took the link
      stopped = true;
      notify('error', 'Another Golden Surface took the relay link. This one is offline.', {
        label: 'Take it back',
        run: () => connect(),
      });
      return;
    }
    if (stopped) return;
    const wait = Math.min(backoff, 30000) * (0.8 + Math.random() * 0.4);
    backoff = Math.min(backoff * 2, 30000);
    retryTimer = setTimeout(connect, wait);
  };
}

export function reconnectNow() {
  backoff = 1000;
  if (!ws && !stopped) connect();
}

export function disconnect() {
  stopped = true;
  ws?.close();
}

function handle(m: any) {
  switch (m.type) {
    case 'welcome':
      if (m.base > getState().browser.ackTwinRev) {
        updateBrowser((b) => {
          b.ackTwinRev = m.base; // rebase: ops at or below base are settled
        });
      }
      setSessions(m.sessions ?? []);
      setUi({ suggested: m.suggested ?? [], sync: m.sync ?? getState().sync });
      return;
    case 'rebase':
      if (m.base > getState().browser.ackTwinRev) updateBrowser((b) => void (b.ackTwinRev = m.base));
      return;
    case 'op':
      return onOp(m, send);
    case 'cmd':
      return onCmd(m, send);
    case 'sessions':
      return setSessions(m.sessions ?? []);
    case 'suggested':
      return setUi({ suggested: m.suggested ?? [] });
    case 'sync':
      setUi({ sync: { status: m.status, classes: m.classes ?? [], detail: m.detail, ts: m.ts } });
      return;
    case 'resync':
      postState(getState().browser);
      return;
    case 'login_request':
      return addLogin(m);
    case 'probe':
      return probe(m.id, m.url);
  }
}

function addLogin(m: any) {
  const req: LoginRequest = { id: m.id, site: m.site, url: m.url, tab: m.tab ?? null, by: m.by ?? 'r',
    reason: m.reason, stage: 'asked' };
  setUi({ logins: [...getState().logins.filter((l) => l.site !== req.site), req] });
}

/** Phone-side session check. On Android, RN's fetch uses the same cookie jar
 *  as the WebViews, so this sees exactly the session the tabs see. */
async function probe(id: string, url: string) {
  try {
    const r = await fetch(url, { credentials: 'include', redirect: 'follow' });
    const body = await r.text();
    const dead = looksLikeLogin(r.url) || /type=["']?password/i.test(body);
    send({ type: 'probe_result', id, status: dead ? 'dead' : 'alive', finalUrl: r.url,
      reason: dead ? 'login wall on the phone' : 'no login wall' });
  } catch (e) {
    send({ type: 'probe_result', id, status: 'unknown', reason: `probe failed: ${String(e)}` });
  }
}

/** Abed finished signing in with his own fingers. `approved` = share with the counsel. */
export async function loginDone(site: string, tabId: string, approved: boolean) {
  const tab = tabById(tabId);
  const url = tab?.url ?? '';
  let cookies: { name: string; value: string }[] = [];
  if (approved && cookieBridge.available) {
    try {
      cookies = await cookieBridge.get(url); // sent only to the relay's twin jar; never stored in the DB
    } catch (e) {
      notify('warn', `Could not export ${site} session to the twin: ${String(e)}`);
    }
  }
  send({ type: 'login_done', site, tab: tabId, url, approved, cookies, owner: tab?.owner });
  if (approved && !cookieBridge.available) {
    notify('warn', `${site}: shared as mirror-only — this build can't hand the session to the twin; the phone stays the driver.`);
  }
}

// ---- telemetry --------------------------------------------------------------------

let postTimer: ReturnType<typeof setTimeout> | null = null;
async function postState(b: BrowserState) {
  const { relayUrl, token } = config();
  try {
    const r = await fetch(relayUrl + '/state', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ state: b }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
  } catch {
    // link-down is already surfaced; hello carries the full state on reconnect
  }
}

onBrowserChange((b) => {
  if (stopped) return; // a replaced client must not overwrite the twin with stale state
  if (postTimer) clearTimeout(postTimer);
  postTimer = setTimeout(() => postState(b), 250);
});

export async function resync(mode: 'replay' | 'adopt-phone') {
  const { relayUrl, token } = config();
  try {
    const r = await fetch(relayUrl + '/sync/resync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ mode }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    notify('info', mode === 'replay' ? 'Resync requested: twin is replaying its ops.' : 'Resync: the twin adopted the phone.');
  } catch (e) {
    notify('error', `Resync failed: ${String(e)}`);
  }
}

export function suggestedOpened(service: string) {
  send({ type: 'suggested_opened', service });
}

export function signal(kind: string, payload: object) {
  send({ type: 'signal', kind, ...payload });
}
