import { StatusBar } from 'expo-status-bar';
import { useEffect, useState } from 'react';
import { ActivityIndicator, AppState, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Banners } from './src/components/BannerStack';
import { Browser } from './src/components/Browser';
import { Najwa } from './src/components/Najwa';
import { Panel } from './src/components/Panel';
import { loadConfig } from './src/config';
import { cookieBridge } from './src/cookies';
import { connect, reconnectNow, signal } from './src/relay';
import { hydrate, setUi, useApp } from './src/state';
import { C, SERIF } from './src/theme';

export default function App() {
  const hydrated = useApp((s) => s.hydrated);
  const surface = useApp((s) => s.surface);
  const link = useApp((s) => s.link);
  const suggestedCount = useApp((s) => s.suggested.filter((x) => x.status === 'open').length);
  const [panel, setPanel] = useState(false);

  useEffect(() => {
    (async () => {
      await loadConfig();
      await hydrate();
      connect();
    })();
    const sub = AppState.addEventListener('change', (st) => {
      // lifecycle is a touch point on the map: background means state is being persisted
      signal('app.lifecycle', { state: st });
      if (st === 'active') reconnectNow();
      else cookieBridge.flush().catch(() => {});
    });
    return () => sub.remove();
  }, []);

  if (!hydrated) {
    return (
      <View style={[s.root, { justifyContent: 'center' }]}>
        <ActivityIndicator color={C.gold} />
      </View>
    );
  }

  return (
    <SafeAreaView style={s.root} edges={['top', 'bottom']}>
      <StatusBar style="light" />
      <View style={s.top}>
        <Seg label="Browser" on={surface === 'browser'} onPress={() => setUi({ surface: 'browser' })} />
        <Seg label="Najwa" on={surface === 'najwa'} onPress={() => setUi({ surface: 'najwa' })} />
        <View style={{ flex: 1 }} />
        <View style={[s.dot, { backgroundColor: link === 'up' ? C.green : link === 'down' ? C.red : C.amber }]} />
        <Pressable onPress={() => setPanel(true)} hitSlop={10} style={{ paddingHorizontal: 10 }}>
          <Text style={s.menu}>
            ☰{suggestedCount ? <Text style={{ color: C.gold }}> {suggestedCount}</Text> : null}
          </Text>
        </Pressable>
      </View>
      <Banners />
      {/* Both surfaces stay mounted: background tabs and the room never stop. */}
      <View style={s.fill}>
        <View style={[s.layer, surface !== 'browser' && s.hidden]} pointerEvents={surface === 'browser' ? 'auto' : 'none'}>
          <Browser />
        </View>
        <View style={[s.layer, surface !== 'najwa' && s.hidden]} pointerEvents={surface === 'najwa' ? 'auto' : 'none'}>
          <Najwa />
        </View>
      </View>
      {panel ? <Panel onClose={() => setPanel(false)} /> : null}
    </SafeAreaView>
  );
}

function Seg({ label, on, onPress }: { label: string; on: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[s.seg, on && s.segOn]}>
      <Text style={[s.segText, on && { color: C.gold }]}>{label}</Text>
    </Pressable>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: C.bg },
  top: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 10, height: 42, backgroundColor: C.bg },
  seg: { paddingHorizontal: 12, paddingVertical: 6, marginRight: 4, borderBottomWidth: 2, borderColor: 'transparent' },
  segOn: { borderColor: C.gold },
  segText: { color: C.muted, fontFamily: SERIF, fontSize: 15, letterSpacing: 1 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  menu: { color: C.muted, fontSize: 20 },
  fill: { flex: 1 },
  layer: { ...StyleSheet.absoluteFill, zIndex: 1 },
  hidden: { opacity: 0, zIndex: 0 },
});
