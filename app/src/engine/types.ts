import type { ComponentType } from 'react';
import type { Tab } from '../types';

/** The engine seam. WebView implements it today; a GeckoView engine (per-tab
 *  contexts, real cookie isolation) would implement the same two things:
 *  a TabView component and the handle it registers. Nothing outside
 *  src/engine/ touches react-native-webview. */
export interface TabHandle {
  /** Run `body` (a JS function body; may return a value or a Promise) in the page. */
  evaluate<T = unknown>(body: string, timeoutMs?: number): Promise<T>;
  screenshot(): Promise<string>;           // base64 PNG
  /** Resolves at the next load end of a real page (not about:blank), or after timeoutMs. */
  waitForLoad(timeoutMs: number): Promise<void>;
  reload(): void;
  goBack(): void;
  goForward(): void;
}

export type EngineEvent =
  | { type: 'nav'; url: string; title: string; loading: boolean; canGoBack: boolean; canGoForward: boolean }
  | { type: 'crash'; reason: string }
  | { type: 'scheme'; url: string; scheme: string; message: string }
  | { type: 'google-blocked'; url: string }
  | { type: 'http-error'; url: string; status: number };

export interface TabViewProps {
  tab: Tab;
  visible: boolean;
  onEvent: (tabId: string, ev: EngineEvent) => void;
  register: (tabId: string, handle: TabHandle | null) => void;
}

export interface Engine {
  name: string;
  TabView: ComponentType<TabViewProps>;
}
