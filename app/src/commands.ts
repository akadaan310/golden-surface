import { handleFor } from './engine';
import { isLocked } from './locked';
import { route } from './routing';
import { blankTab, getState, notify, tabById, updateBrowser } from './state';
import type { Owner } from './types';

/** Phone side of the sync model (docs/SYNC.md) and the remote command set.
 *
 *  Twin ops (open/newtab/closetab) carry a twin rev. They are processed
 *  strictly in order: rev == ackTwinRev+1 is applied (or rejected), older
 *  revs are duplicates and ignored, a gap is NACKed so the relay resends.
 *  Non-mutating commands (read/shot/tap/type) are answered directly. */

export type Send = (m: object) => void;

let chain: Promise<void> = Promise.resolve();

export function onOp(m: { rev: number; op: string; params: any; id?: string }, send: Send) {
  chain = chain
    .then(() => processOp(m, send))
    .catch((e) => {
      notify('error', `Remote op failed: ${String(e)}`);
    });
}

async function processOp(m: { rev: number; op: string; params: any; id?: string }, send: Send) {
  const ack = getState().browser.ackTwinRev;
  if (m.rev <= ack) return; // duplicate delivery
  if (m.rev !== ack + 1) {
    send({ type: 'nack', ack });
    return;
  }
  let rejected: string | null = null;
  let data: object | undefined;
  const p = m.params;
  if (m.op === 'newtab') {
    const owner: Owner = p.owner;
    updateBrowser((b) => {
      if (!b.tabs.some((t) => t.id === p.tab)) b.tabs.push(blankTab(owner, p.url ?? 'about:blank', p.tab));
      b.activeTabId = p.tab;
      b.ackTwinRev = m.rev;
    });
    data = { tab: p.tab, owner };
  } else if (m.op === 'open') {
    const r = route(p.url);
    const tab = tabById(p.tab);
    if (!tab) rejected = 'no such tab';
    else if (r.kind === 'scheme') rejected = `scheme not supported: ${r.message}`;
    else if (r.kind === 'surface') rejected = 'seurl://golden addresses resolve on the relay, not as a page';
    if (rejected) {
      updateBrowser((b) => {
        b.ackTwinRev = m.rev;
      });
    } else {
      updateBrowser((b) => {
        const t = b.tabs.find((x) => x.id === p.tab)!;
        t.src = { uri: p.url, n: t.src.n + 1 };
        t.url = p.url;
        t.loading = true;
        b.ackTwinRev = m.rev;
      });
      await handleFor(p.tab)?.waitForLoad(20000);
      const t = tabById(p.tab);
      data = { url: t?.url, title: t?.title };
    }
  } else if (m.op === 'closetab') {
    if (!tabById(p.tab)) rejected = 'no such tab';
    else if (isLocked(p.tab)) rejected = 'locked tab';
    updateBrowser((b) => {
      if (!rejected) {
        b.tabs = b.tabs.filter((t) => t.id !== p.tab);
        if (b.activeTabId === p.tab) b.activeTabId = b.tabs.length ? b.tabs[b.tabs.length - 1].id : null;
      }
      b.ackTwinRev = m.rev;
    });
  } else {
    rejected = `unknown op ${m.op}`;
    updateBrowser((b) => {
      b.ackTwinRev = m.rev;
    });
  }
  if (rejected) notify('warn', `Remote ${m.op} refused: ${rejected}`);
  send({ type: 'ack', rev: m.rev, id: m.id, rejected, data, state: getState().browser });
}

// ---- non-mutating commands -------------------------------------------------------

const READ_JS = `return {url: location.href, title: document.title,
  text: (document.body ? document.body.innerText : '').slice(0, 200000)};`;

const TAP_JS = (x: number, y: number) => `var el = document.elementFromPoint(${x}, ${y});
  if (!el) throw new Error('nothing at ${x},${y}');
  var o = {bubbles: true, cancelable: true, clientX: ${x}, clientY: ${y}, view: window};
  ['pointerdown','mousedown','pointerup','mouseup'].forEach(function(t){
    el.dispatchEvent(new (t.indexOf('pointer')===0 && window.PointerEvent ? PointerEvent : MouseEvent)(t, o)); });
  if (el.focus) el.focus();
  el.click();
  return {tag: el.tagName.toLowerCase(), text: (el.innerText || el.value || '').slice(0, 80)};`;

// Agents never type into password fields: refused here, in the page, before any keystroke.
const TYPE_JS = (text: string) => `var el = document.activeElement;
  if (!el || el === document.body) throw new Error('no focused field — tap one first');
  var ac = (el.getAttribute('autocomplete') || '').toLowerCase();
  var nm = ((el.name || '') + ' ' + (el.id || '')).toLowerCase();
  if ((el.type || '').toLowerCase() === 'password' || ac.indexOf('password') >= 0 || /pass(word|wd)?\\b|pin\\b|otp/.test(nm))
    throw new Error('refused: password field — Abed types these himself');
  var t = ${JSON.stringify(text)};
  if (el.isContentEditable) { document.execCommand('insertText', false, t); }
  else if ('value' in el) {
    var proto = el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
    setter.call(el, (el.value || '') + t);
    el.dispatchEvent(new Event('input', {bubbles: true}));
    el.dispatchEvent(new Event('change', {bubbles: true}));
  } else throw new Error('focused element is not editable');
  return {typed: t.length, field: el.name || el.id || el.tagName.toLowerCase()};`;

// Structures: the page's affordances, indexed, so an LLM acts by number instead
// of by pixel. Values are never read; password fields are marked fingers-only.
const PW_TEST = `function gsPw(el){var ac=(el.getAttribute('autocomplete')||'').toLowerCase();
  var nm=((el.name||'')+' '+(el.id||'')).toLowerCase();
  return (el.type||'').toLowerCase()==='password'||ac.indexOf('password')>=0||/pass(word|wd)?\\b|pin\\b|otp/.test(nm);}`;

const STRUCTURES_JS = `${PW_TEST}
  var sel='a[href],button,input,textarea,select,[role=button],[role=link],[contenteditable=true]';
  var out=[], i=0;
  document.querySelectorAll('[data-gs-i]').forEach(function(e){e.removeAttribute('data-gs-i');});
  document.querySelectorAll(sel).forEach(function(el){
    if(out.length>=200) return;
    var r=el.getBoundingClientRect(); if(!r.width||!r.height) return;
    var tag=el.tagName.toLowerCase(), type=(el.type||'').toLowerCase();
    if(tag==='input'&&(type==='hidden')) return;
    var kind=tag==='a'?'link':(tag==='input'&&!/submit|button|image|reset|checkbox|radio/.test(type))||tag==='textarea'||el.isContentEditable?'field':tag==='select'?'select':'button';
    var label=(el.getAttribute('aria-label')||el.innerText||el.value&&kind==='button'&&el.value||el.placeholder||el.name||el.title||'').trim().replace(/\\s+/g,' ').slice(0,80);
    el.setAttribute('data-gs-i', String(i));
    var e={i:i,kind:kind,label:label};
    if(kind==='link') e.href=el.href;
    if(kind==='field'){e.name=el.name||el.id||null;e.type=type||tag;if(gsPw(el))e.fingersOnly=true;}
    out.push(e); i++;
  });
  return {url:location.href,title:document.title,count:out.length,items:out};`;

const ACT_JS = (index: number, kind: string, text: string) => `${PW_TEST}
  var el=document.querySelector('[data-gs-i="${index}"]');
  if(!el) throw new Error('no element ${index}: the page changed — read structures again');
  if(gsPw(el)) throw new Error('refused: password field — Abed types these himself');
  var k=${JSON.stringify(kind)}, t=${JSON.stringify(text)};
  if(k==='tap'){ if(el.focus)el.focus(); el.click(); }
  else if(k==='fill'){
    if(el.isContentEditable){el.focus();document.execCommand('insertText',false,t);}
    else if('value' in el){var proto=el.tagName==='TEXTAREA'?HTMLTextAreaElement.prototype:el.tagName==='SELECT'?HTMLSelectElement.prototype:HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value').set.call(el,t);
      el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}
    else throw new Error('element ${index} is not fillable');
  } else if(k==='submit'){ var f=el.form||el.closest('form');
    if(f){ f.requestSubmit?f.requestSubmit():f.submit(); } else el.click(); }
  else throw new Error('act kind must be tap, fill or submit');
  return {done:k,index:${index},tag:el.tagName.toLowerCase()};`;

export async function onCmd(m: { id: string; cmd: string; params: any }, send: Send) {
  const p = m.params;
  const h = handleFor(p.tab);
  const reply = (ok: boolean, x: { data?: unknown; error?: string }) => send({ type: 'result', id: m.id, ok, ...x });
  if (!tabById(p.tab) || !h) return reply(false, { error: 'no such tab' });
  try {
    switch (m.cmd) {
      case 'read':
        return reply(true, { data: await h.evaluate(READ_JS) });
      case 'shot':
        return reply(true, { data: { png: await h.screenshot() } });
      case 'tap':
        return reply(true, { data: await h.evaluate(TAP_JS(Number(p.x), Number(p.y))) });
      case 'type':
        return reply(true, { data: await h.evaluate(TYPE_JS(String(p.text ?? ''))) });
      case 'structures':
        return reply(true, { data: await h.evaluate(STRUCTURES_JS) });
      case 'act':
        return reply(true, { data: await h.evaluate(ACT_JS(Number(p.index), String(p.kind), String(p.text ?? ''))) });
      default:
        return reply(false, { error: `unknown cmd ${m.cmd}` });
    }
  } catch (e: any) {
    return reply(false, { error: String(e?.message ?? e) });
  }
}
