import { explainScheme } from './schemes';

/** URL routing seam. http/https (and the few in-page schemes a browser must
 *  allow) load normally; every other scheme goes to schemes.ts — the one
 *  handler module. Nothing is built behind that seam yet. */
export type Route = { kind: 'web'; url: string } | { kind: 'scheme'; scheme: string; message: string };

const WEB = new Set(['http', 'https', 'about', 'data', 'blob', 'javascript']);

export function schemeOf(url: string) {
  const m = /^([a-z][a-z0-9+.-]*):/i.exec(url.trim());
  return m ? m[1].toLowerCase() : '';
}

export function route(url: string): Route {
  const s = schemeOf(url);
  if (WEB.has(s)) return { kind: 'web', url };
  return { kind: 'scheme', scheme: s || '(none)', message: explainScheme(s, url) };
}

/** What Abed typed in the address bar -> a URL. */
export function normalizeInput(input: string) {
  const t = input.trim();
  if (!t) return 'about:blank';
  if (schemeOf(t)) return t;
  if (/^[^\s]+\.[^\s]{2,}(\/.*)?$/.test(t)) return 'https://' + t;
  return 'https://www.google.com/search?q=' + encodeURIComponent(t);
}

export function siteOf(url: string) {
  const m = /^[a-z]+:\/\/([^/:?#]+)/i.exec(url || '');
  if (!m) return '';
  const h = m[1].toLowerCase();
  return h.startsWith('www.') ? h.slice(4) : h;
}

export const LOGIN_MARKERS = ['/login', '/signin', '/sign_in', '/sign-in', '/auth', 'servicelogin',
  'accounts.google.com/v3/signin', '/session/new'];

export const looksLikeLogin = (url: string) => LOGIN_MARKERS.some((m) => url.toLowerCase().includes(m));
