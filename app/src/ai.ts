import { domainOfUrl } from './domains';
import { siteOf } from './routing';

/** Which AI surface, if any, a URL is. Detection is by address only: the
 *  browser knows an LLM is engaged the moment a tab lands on one. */
const HOSTS: Array<[RegExp, string]> = [
  [/(^|\.)gemini\.google\.com$/, 'gemini'],
  [/(^|\.)chatgpt\.com$/, 'chatgpt'],
  [/(^|\.)chat\.openai\.com$/, 'chatgpt'],
  [/(^|\.)claude\.ai$/, 'claude'],
  [/(^|\.)perplexity\.ai$/, 'perplexity'],
  [/(^|\.)copilot\.microsoft\.com$/, 'copilot'],
  [/(^|\.)duck\.ai$/, 'duck.ai'],
];

// Google AI Mode is a search results page with udm=50.
const GOOGLE_AI_MODE = /^https?:\/\/(www\.)?google\.[a-z.]+\/search\?(.*&)?udm=50(&|$)/i;

export function aiOf(url: string): string | undefined {
  if (GOOGLE_AI_MODE.test(url || '')) return 'google-ai-mode';
  const host = siteOf(url);
  if (!host) return undefined;
  return HOSTS.find(([re]) => re.test(host))?.[1];
}

/** The page context a tab contributes to a question: its address, title and a
 *  window of its text. A tab on a shared (signed-in) session gives only its
 *  address and title — never its page text. */
export interface TabContext {
  url: string;
  title: string;
  text?: string;
}

const MAX_Q = 1800; // keep the whole URL well under common length limits

/** A question plus the open tab's context, composed into one URL: an unsigned
 *  Google AI Mode query. The URL carries everything the answer needs. */
export function askUrl(question: string, ctx: TabContext | null): string {
  let q = question.trim();
  if (ctx) {
    const d = domainOfUrl(ctx.url);
    const head = `\n\nMy open tab: ${ctx.title || siteOf(ctx.url)} — ${ctx.url}${d ? ` (.${d.tld}: ${d.class})` : ''}`;
    const room = MAX_Q - q.length - head.length - 8;
    const text = ctx.text && room > 80 ? `\n${ctx.text.replace(/\s+/g, ' ').trim().slice(0, room)}` : '';
    q += head + text;
  }
  return 'https://www.google.com/search?udm=50&q=' + encodeURIComponent(q.slice(0, MAX_Q));
}
