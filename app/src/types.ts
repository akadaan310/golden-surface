export type Owner = 'abed' | 'r' | 'n';

export const SEAT_NAME: Record<Owner, string> = { abed: 'Abed', r: 'ر', n: 'ن' };
export const SEAT_COLOR: Record<Owner, string> = { abed: '#c9a227', r: '#5fb3a1', n: '#9b87c9' };

export interface Tab {
  id: string;
  owner: Owner;
  url: string;          // last committed URL (observed on the phone)
  title: string;
  signedIn: boolean;    // site has an alive/expiring shared session
  createdAt: string;
  src: { uri: string; n: number }; // what the engine was told to load
  crashed?: boolean;
  loading?: boolean;
}

/** Full browser state — the shape the relay's /state and twin share. */
export interface BrowserState {
  rev: number;          // phone_rev: bumps on every phone-side change
  ackTwinRev: number;   // last twin op processed (applied or rejected)
  tabs: Tab[];
  activeTabId: string | null;
}

export interface SessionRow {
  site: string;
  site_id: string;
  base_url: string;
  session_id: string;
  owner: Owner;
  status: 'alive' | 'expiring' | 'dead' | 'unknown';
  last_seen_alive_at: string | null;
  check_failures: number;
  approved_by_abed_at: string | null;
  check_via: 'twin' | 'phone';
}

export interface LoginRequest {
  id: string;
  site: string;
  url: string;
  tab: string | null;
  by: Owner;
  reason?: string | null;
  stage: 'asked' | 'signing-in';
  tabId?: string;
}

export interface Suggested {
  service: string;
  signup_url: string;
  why: string | null;
  added_by: Owner;
  status: string;
}

export interface SyncStatus {
  status: 'unknown' | 'converged' | 'diverged';
  classes: string[];
  detail?: Record<string, string> | null;
  ts?: string;
}

export interface Notice {
  id: string;
  level: 'error' | 'warn' | 'info';
  text: string;
  action?: { label: string; run: () => void };
}
