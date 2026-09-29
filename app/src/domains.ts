import { siteOf } from './routing';

/** Domain-oriented navigation: what class of place an address is, from its
 *  domain. Same table as relay/domains.py and luna-foundry/lib/lens.js. */
const CLASSES: Record<string, string> = {
  gov: 'government — public records and authoritative data',
  mil: 'military',
  edu: 'education and research',
  org: 'organizations and communities',
  com: 'commerce and companies',
  net: 'networks and services',
  int: 'international organizations',
  io: 'technology', dev: 'technology', app: 'technology', ai: 'technology',
};

export interface DomainClass { tld: string; class: string; country?: string }

export function domainClass(host: string): DomainClass | undefined {
  if (!host) return undefined;
  const labels = host.toLowerCase().replace(/\.$/, '').split('.');
  const tld = labels[labels.length - 1];
  const second = labels.length > 1 ? labels[labels.length - 2] : '';
  if (tld.length === 2 && CLASSES[second]) return { tld: `${second}.${tld}`, class: CLASSES[second], country: tld };
  if (CLASSES[tld]) return { tld, class: CLASSES[tld] };
  if (tld.length === 2) return { tld, class: 'country', country: tld };
  return { tld, class: 'general' };
}

export const domainOfUrl = (url: string) => domainClass(siteOf(url));
