import { useEffect, useState } from 'react';
import { config } from './config';

/** Tails the conference bus (/bus/stream, SSE). RN has no EventSource, so this
 *  reads the stream through XHR progress events and resumes from the last
 *  seq after any drop (backoff 1s -> 15s). */

export interface BusEvent {
  seq: number;
  ts: string;
  kind: string;
  actor: string | null;
  payload: any;
}

export const CONFERENCE_KINDS = ['round.opened', 'turn.saved', 'chair.direction', 'scribe.note', 'round.closed'];

export function useBus() {
  const [events, setEvents] = useState<BusEvent[]>([]);
  const [live, setLive] = useState<'connecting' | 'live' | 'down'>('connecting');

  useEffect(() => {
    let xhr: XMLHttpRequest | null = null;
    let lastSeq = 0;
    let backoff = 1000;
    let timer: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const open = () => {
      const { relayUrl, token } = config();
      const x = new XMLHttpRequest();
      xhr = x;
      let seen = 0;
      let buf = '';
      x.open('GET', `${relayUrl}/bus/stream?since=${lastSeq}&kinds=${CONFERENCE_KINDS.join(',')}`);
      x.setRequestHeader('Accept', 'text/event-stream');
      x.setRequestHeader('Authorization', 'Bearer ' + token);
      x.onprogress = () => {
        setLive('live');
        backoff = 1000;
        buf += x.responseText.slice(seen);
        seen = x.responseText.length;
        const parts = buf.split('\n\n');
        buf = parts.pop() ?? '';
        const fresh: BusEvent[] = [];
        for (const block of parts) {
          const data = block.split('\n').filter((l) => l.startsWith('data: ')).map((l) => l.slice(6)).join('\n');
          if (!data) continue;
          try {
            const ev: BusEvent = JSON.parse(data);
            if (ev.seq > lastSeq) {
              lastSeq = ev.seq;
              fresh.push(ev);
            }
          } catch {}
        }
        if (fresh.length) setEvents((prev) => [...prev, ...fresh]);
        if (seen > 2_000_000) {
          // XHR keeps the whole body; recycle the stream and resume from lastSeq
          xhr = null;
          x.abort();
          open();
        }
      };
      const retry = () => {
        if (closed || xhr !== x) return;
        setLive('down');
        timer = setTimeout(open, backoff);
        backoff = Math.min(backoff * 2, 15000);
      };
      x.onerror = retry;
      x.onload = retry; // server closed the stream
      x.send();
    };
    open();
    return () => {
      closed = true;
      if (timer) clearTimeout(timer);
      xhr?.abort();
    };
  }, []);

  return { events, live };
}
