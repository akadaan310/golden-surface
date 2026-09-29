import type { Owner, Tab } from './types';

/** The three locked tabs. They are always present, always first, and cannot be
 *  closed — not by Abed's fingers, not by a remote closetab. Their pages can be
 *  navigated like any tab; ⌂ returns a locked tab to its home URL.
 *
 *  The `lock-` id prefix is the marker the relay and twin also check, so the
 *  rule holds on every side of the sync model without a schema change. */
export const LOCK_PREFIX = 'lock-';

export interface LockedDef {
  id: string;
  owner: Owner;
  label: string;
  home: string;
}

export const LOCKED: LockedDef[] = [
  {
    id: 'lock-luna',
    owner: 'r',
    label: 'Luna',
    home: process.env.EXPO_PUBLIC_LUNA_URL ?? 'https://lunar-foundry.vercel.app/',
  },
  {
    id: 'lock-acsp',
    owner: 'n',
    label: 'ACSP',
    home: process.env.EXPO_PUBLIC_ACSP_URL ?? 'https://acsp-one.vercel.app/',
  },
  {
    id: 'lock-trial',
    owner: 'abed',
    label: 'Trial',
    // Pending: the trial resource does not exist yet. Until it does, this is the
    // ACSP protocol page. Set EXPO_PUBLIC_TRIAL_URL once the trial is opened.
    home: process.env.EXPO_PUBLIC_TRIAL_URL ?? 'https://acsp-one.vercel.app/protocol',
  },
];

export const isLocked = (id: string | null | undefined) => !!id && id.startsWith(LOCK_PREFIX);
export const lockedDef = (id: string) => LOCKED.find((d) => d.id === id);

/** Put the locked tabs back if anything removed them, fix their owners, and keep
 *  them at the front of the strip in their declared order. Tabs the user opened
 *  keep their order after them. `make` builds a fresh tab when one is missing. */
export function withLocked(tabs: Tab[], make: (d: LockedDef) => Tab): Tab[] {
  const locked = LOCKED.map((d) => {
    const t = tabs.find((x) => x.id === d.id);
    return t ? { ...t, owner: d.owner, locked: true } : { ...make(d), locked: true };
  });
  return [...locked, ...tabs.filter((t) => !isLocked(t.id))];
}
