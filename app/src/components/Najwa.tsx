import { useEffect, useRef } from 'react';
import { FlatList, StyleSheet, Text, View } from 'react-native';
import { useBus, type BusEvent } from '../bus';
import { C, SERIF } from '../theme';
import { SEAT_COLOR, SEAT_NAME, type Owner } from '../types';

/** Najwa — the room. Tails the conference bus and renders it live:
 *  rounds, each turn under its speaker's name, the Chair, the Scribe. */
export function Najwa() {
  const { events, live } = useBus();
  const list = useRef<FlatList<BusEvent>>(null);
  const atBottom = useRef(true);

  useEffect(() => {
    if (atBottom.current) setTimeout(() => list.current?.scrollToEnd({ animated: true }), 50);
  }, [events.length]);

  return (
    <View style={s.room}>
      <View style={s.head}>
        <Text style={s.title}>NAJWA</Text>
        <View style={s.liveRow}>
          <View style={[s.dot, { backgroundColor: live === 'live' ? C.gold : live === 'down' ? C.red : C.faint }]} />
          <Text style={[s.liveText, live === 'down' && { color: C.red }]}>
            {live === 'live' ? 'in session' : live === 'down' ? 'bus unreachable — retrying' : 'joining'}
          </Text>
        </View>
      </View>
      <FlatList
        ref={list}
        data={events}
        keyExtractor={(e) => String(e.seq)}
        renderItem={({ item }) => <Entry ev={item} />}
        contentContainerStyle={s.body}
        onScroll={(e) => {
          const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
          atBottom.current = contentOffset.y + layoutMeasurement.height >= contentSize.height - 80;
        }}
        scrollEventThrottle={100}
        ListEmptyComponent={<Text style={s.empty}>The room is quiet. Nothing has been said yet.</Text>}
      />
    </View>
  );
}

function Entry({ ev }: { ev: BusEvent }) {
  const p = ev.payload ?? {};
  const time = new Date(ev.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  switch (ev.kind) {
    case 'round.opened':
      return (
        <View style={s.round}>
          <View style={s.rule} />
          <Text style={s.roundText}>
            ROUND {p.round ?? ''}{p.topic ? ` · ${String(p.topic).toUpperCase()}` : ''}
          </Text>
          <View style={s.rule} />
        </View>
      );
    case 'round.closed':
      return (
        <View style={s.closed}>
          <Text style={s.closedText}>round {p.round ?? ''} closed · {time}</Text>
          {p.summary ? <Text style={s.closedSummary}>{p.summary}</Text> : null}
        </View>
      );
    case 'turn.saved': {
      const sp = (p.speaker ?? ev.actor) as Owner;
      return (
        <View style={s.turn}>
          <View style={s.speakerRow}>
            <Text style={[s.speaker, { color: SEAT_COLOR[sp] ?? C.muted }]}>{SEAT_NAME[sp] ?? sp}</Text>
            <Text style={s.time}>{time}</Text>
          </View>
          <Text style={s.turnText}>{p.text}</Text>
        </View>
      );
    }
    case 'chair.direction':
      return (
        <View style={s.chair}>
          <Text style={s.chairLabel}>THE CHAIR</Text>
          <Text style={s.chairText}>{p.text}</Text>
        </View>
      );
    case 'scribe.note':
      return (
        <View style={s.scribe}>
          <Text style={s.scribeText}>
            <Text style={s.scribeLabel}>scribe — </Text>
            {p.text}
          </Text>
        </View>
      );
    default:
      return null;
  }
}

const s = StyleSheet.create({
  room: { flex: 1, backgroundColor: C.bg },
  head: { paddingHorizontal: 22, paddingTop: 14, paddingBottom: 10, borderBottomWidth: StyleSheet.hairlineWidth, borderColor: C.line },
  title: { color: C.gold, fontFamily: SERIF, fontSize: 18, letterSpacing: 6 },
  liveRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  dot: { width: 6, height: 6, borderRadius: 3, marginRight: 8 },
  liveText: { color: C.muted, fontSize: 11, letterSpacing: 1 },
  body: { paddingHorizontal: 22, paddingVertical: 18 },
  empty: { color: C.faint, fontFamily: SERIF, fontStyle: 'italic', textAlign: 'center', marginTop: 60 },
  round: { flexDirection: 'row', alignItems: 'center', marginTop: 18, marginBottom: 14 },
  rule: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: C.gold, opacity: 0.5 },
  roundText: { color: C.gold, fontSize: 11, letterSpacing: 3, marginHorizontal: 12 },
  closed: { alignItems: 'center', marginVertical: 16 },
  closedText: { color: C.faint, fontSize: 11, letterSpacing: 2 },
  closedSummary: { color: C.muted, fontFamily: SERIF, fontStyle: 'italic', marginTop: 6, textAlign: 'center' },
  turn: { marginBottom: 18 },
  speakerRow: { flexDirection: 'row', alignItems: 'baseline', marginBottom: 4 },
  speaker: { fontFamily: SERIF, fontSize: 15, marginRight: 10 },
  time: { color: C.faint, fontSize: 10, writingDirection: 'ltr' },
  turnText: { color: C.text, fontFamily: SERIF, fontSize: 16, lineHeight: 24 },
  chair: { borderLeftWidth: 2, borderColor: C.gold, paddingLeft: 12, marginBottom: 18, marginLeft: 4 },
  chairLabel: { color: C.gold, fontSize: 10, letterSpacing: 2, marginBottom: 3 },
  chairText: { color: C.text, fontFamily: SERIF, fontStyle: 'italic', fontSize: 15, lineHeight: 22 },
  scribe: { marginBottom: 14, marginLeft: 16 },
  scribeText: { color: C.muted, fontSize: 13, lineHeight: 19 },
  scribeLabel: { color: C.faint, fontStyle: 'italic' },
});
