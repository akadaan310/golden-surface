import type { Engine, TabHandle } from './types';
import { WebViewEngine } from './webview';

export const engine: Engine = WebViewEngine;

const handles = new Map<string, TabHandle>();
export const registerHandle = (id: string, h: TabHandle | null) => {
  if (h) handles.set(id, h);
  else handles.delete(id);
};
export const handleFor = (id: string) => handles.get(id);
export type { EngineEvent, TabHandle } from './types';
