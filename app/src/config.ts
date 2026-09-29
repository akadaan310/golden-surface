import AsyncStorage from '@react-native-async-storage/async-storage';

/** Relay endpoint + the app's seat token. Defaults come from app/.env
 *  (EXPO_PUBLIC_RELAY_URL / EXPO_PUBLIC_APP_TOKEN, gitignored); Abed can
 *  change both in Settings. The token is a relay seat token, not a site secret. */
export interface Config { relayUrl: string; token: string }

const KEY = 'gs.config.v1';
let cfg: Config = {
  relayUrl: process.env.EXPO_PUBLIC_RELAY_URL ?? 'http://127.0.0.1:8490',
  token: process.env.EXPO_PUBLIC_APP_TOKEN ?? '',
};

export async function loadConfig(): Promise<Config> {
  const raw = await AsyncStorage.getItem(KEY);
  if (raw) cfg = { ...cfg, ...JSON.parse(raw) };
  return cfg;
}

export async function saveConfig(next: Config) {
  cfg = { relayUrl: next.relayUrl.replace(/\/+$/, ''), token: next.token.trim() };
  await AsyncStorage.setItem(KEY, JSON.stringify(cfg));
}

export const config = () => cfg;
export const wsUrl = () => cfg.relayUrl.replace(/^http/, 'ws') + '/ws?token=' + encodeURIComponent(cfg.token);
