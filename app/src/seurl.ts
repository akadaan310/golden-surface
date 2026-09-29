/** seurl://golden — the Golden Surface as addresses. Same grammar as relay/seurl.py.
 *
 *   seurl://golden/map                          the surface map
 *   seurl://golden/tab/{id}                     one tab
 *   seurl://golden/tab/{id}/scroll?from=&len=   a window of the tab's text
 *   seurl://golden/tab/{id}/open?url=           open a URL in the tab
 *
 *  On the phone these resolve only from the address bar (Abed's fingers) or the
 *  relay. A page that navigates to seurl:// is refused by the engine. */
export const PREFIX = 'seurl://golden';

export type Address =
  | { verb: 'map'; params: Record<string, string> }
  | { verb: 'tab' | 'scroll' | 'open'; tab: string; params: Record<string, string> };

export function parseAddress(u: string): Address | null {
  const m = /^seurl:\/\/golden(\/[^?#]*)?(\?[^#]*)?$/i.exec(u.trim());
  if (!m) return null;
  const segs = (m[1] || '').split('/').filter(Boolean).map(decodeURIComponent);
  const params: Record<string, string> = {};
  new URLSearchParams((m[2] || '').slice(1)).forEach((v, k) => (params[k] = v));
  if (!segs.length || (segs.length === 1 && segs[0] === 'map')) return { verb: 'map', params };
  if (segs[0] === 'tab' && segs[1] && segs.length <= 3) {
    const verb = (segs[2] ?? 'tab') as 'tab' | 'scroll' | 'open';
    if (!['tab', 'scroll', 'open'].includes(verb)) return null;
    if (verb === 'open' && !params.url) return null;
    return { verb, tab: segs[1], params };
  }
  return null;
}

export const addressOf = (tabId?: string) => (tabId ? `${PREFIX}/tab/${tabId}` : `${PREFIX}/map`);
