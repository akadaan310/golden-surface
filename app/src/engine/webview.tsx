import { memo, useEffect, useMemo, useRef } from 'react';
import { StyleSheet, View } from 'react-native';
import { captureRef } from 'react-native-view-shot';
import { WebView, type WebViewMessageEvent } from 'react-native-webview';
import { route } from '../routing';
import type { Engine, TabHandle, TabViewProps } from './types';

/**
 * WebView engine.
 *
 * Cookie decision: Android's CookieManager is one jar per app process, and
 * react-native-webview has no per-WebView profile API. Tabs therefore SHARE
 * one jar, deliberately: a site Abed signs into once is signed in for every
 * tab and every seat — which is the session rule ("sessions are shared by
 * design"). Ownership is a tab attribute, not a cookie partition. Cost: one
 * account per site at a time. `incognito` is never set — on Android it wipes
 * the whole app-wide jar. The jar is flushed to disk on every page finish by
 * react-native-webview, so cookies and localStorage survive restarts.
 *
 * Google SSO: WebView's default UA carries "; wv", which Google blocks. We
 * present a Chrome-mobile UA; if Google still refuses, the page is detected
 * and the app offers the Custom Tab path (see LoginBanner).
 */
export const UA =
  'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36';

const GOOGLE_BLOCK_PROBE = `(function(){try{
  if(!/accounts\\.google\\.com/.test(location.host))return;
  var t=(document.body&&document.body.innerText)||'';
  if(/disallowed_useragent|browser or app may not be secure|Couldn.t sign you in/i.test(t))
    window.ReactNativeWebView.postMessage(JSON.stringify({__gsEvent:'google-blocked',url:location.href}));
}catch(e){}})();true;`;

function WebTab({ tab, visible, onEvent, register }: TabViewProps) {
  const ref = useRef<WebView>(null);
  const shotRef = useRef<View>(null);
  const pending = useRef(new Map<string, (m: { ok: boolean; v?: unknown; e?: string }) => void>());
  const loadWaiters = useRef<Array<() => void>>([]);

  // A load is requested by bumping src.n (open, address bar, restore). Page-driven
  // navigation only updates tab.url, never src, so the engine never reloads on its own.
  const source = useMemo(() => ({ uri: tab.src.uri }), [tab.src.n]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const handle: TabHandle = {
      evaluate<T>(body: string, timeoutMs = 15000) {
        const id = Math.random().toString(36).slice(2);
        return new Promise<T>((resolve, reject) => {
          const timer = setTimeout(() => {
            pending.current.delete(id);
            reject(new Error('page did not answer'));
          }, timeoutMs);
          pending.current.set(id, (m) => {
            clearTimeout(timer);
            m.ok ? resolve(m.v as T) : reject(new Error(m.e));
          });
          const post = (x: string) => `window.ReactNativeWebView.postMessage(JSON.stringify(Object.assign({__gs:${JSON.stringify(id)}},${x})))`;
          ref.current?.injectJavaScript(`(function(){try{Promise.resolve((function(){${body}})()).then(
            function(v){${post('{ok:true,v:v}')}},function(e){${post('{ok:false,e:String(e)}')}});}
            catch(e){${post('{ok:false,e:String(e)}')}}})();true;`);
        });
      },
      screenshot: () => captureRef(shotRef, { format: 'png', result: 'base64' }),
      waitForLoad(timeoutMs) {
        return new Promise((resolve) => {
          const t = setTimeout(resolve, timeoutMs);
          loadWaiters.current.push(() => {
            clearTimeout(t);
            resolve();
          });
        });
      },
      reload: () => ref.current?.reload(),
      goBack: () => ref.current?.goBack(),
      goForward: () => ref.current?.goForward(),
    };
    register(tab.id, handle);
    return () => register(tab.id, null);
  }, [tab.id, register]);

  const onMessage = (e: WebViewMessageEvent) => {
    let m: any;
    try {
      m = JSON.parse(e.nativeEvent.data);
    } catch {
      return;
    }
    if (m && m.__gs) {
      pending.current.get(m.__gs)?.(m);
      pending.current.delete(m.__gs);
    } else if (m && m.__gsEvent === 'google-blocked') {
      onEvent(tab.id, { type: 'google-blocked', url: m.url });
    }
  };

  return (
    <View
      style={[StyleSheet.absoluteFill, { opacity: visible ? 1 : 0, zIndex: visible ? 1 : 0 }]}
      pointerEvents={visible ? 'auto' : 'none'}
    >
      <View ref={shotRef} collapsable={false} style={styles.fill}>
        <WebView
          ref={ref}
          source={source}
          style={styles.web}
          userAgent={UA}
          incognito={false}
          thirdPartyCookiesEnabled
          sharedCookiesEnabled
          domStorageEnabled
          javaScriptEnabled
          cacheEnabled
          setSupportMultipleWindows={false}
          allowsBackForwardNavigationGestures
          mediaPlaybackRequiresUserAction
          originWhitelist={['*']}
          onShouldStartLoadWithRequest={(req) => {
            const r = route(req.url);
            if (r.kind === 'web') return true;
            onEvent(tab.id, { type: 'scheme', url: req.url, scheme: r.scheme, message: r.message });
            return false;
          }}
          onLoadEnd={() => {
            loadWaiters.current.splice(0).forEach((f) => f());
            ref.current?.injectJavaScript(GOOGLE_BLOCK_PROBE);
          }}
          onNavigationStateChange={(n) =>
            onEvent(tab.id, {
              type: 'nav', url: n.url, title: n.title ?? '', loading: n.loading ?? false,
              canGoBack: n.canGoBack, canGoForward: n.canGoForward,
            })
          }
          onHttpError={(e) =>
            e.nativeEvent.statusCode >= 500 &&
            onEvent(tab.id, { type: 'http-error', url: e.nativeEvent.url, status: e.nativeEvent.statusCode })
          }
          onRenderProcessGone={(e) =>
            onEvent(tab.id, { type: 'crash', reason: e.nativeEvent.didCrash ? 'renderer crashed' : 'renderer killed for memory' })
          }
          onMessage={onMessage}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  fill: { flex: 1, backgroundColor: '#0b0b0c' },
  web: { flex: 1, backgroundColor: '#ffffff' },
});

export const WebViewEngine: Engine = { name: 'webview', TabView: memo(WebTab) };
