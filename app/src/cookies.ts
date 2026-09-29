import { requireOptionalNativeModule } from 'expo';

/** Bridge to the app-wide Android cookie jar (modules/golden-cookies).
 *  Present in the APK; absent in Expo Go, where shared sessions become
 *  mirror-only (the phone drives, the twin mirrors state).
 *  Used for exactly two things: handing an Abed-approved session to the twin,
 *  and flushing the jar to disk when the app backgrounds. */
interface Native {
  getCookie(url: string): Promise<string | null>;
  flush(): Promise<void>;
}

const native = requireOptionalNativeModule<Native>('GoldenCookies');

export const cookieBridge = {
  available: !!native,
  async get(url: string) {
    if (!native) return [];
    const raw = (await native.getCookie(url)) ?? '';
    return raw
      .split(';')
      .map((p) => p.trim())
      .filter(Boolean)
      .map((p) => {
        const i = p.indexOf('=');
        return { name: i < 0 ? p : p.slice(0, i), value: i < 0 ? '' : p.slice(i + 1) };
      });
  },
  async flush() {
    await native?.flush();
  },
};
