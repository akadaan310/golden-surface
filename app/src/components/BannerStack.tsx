import { ScrollView, StyleSheet } from 'react-native';
import { LinkBanner, Notices, SessionBanner, SyncBanner } from './Banners';
import { LoginBanners } from './LoginBanner';

export function Banners() {
  return (
    <ScrollView style={s.stack} contentContainerStyle={{ flexGrow: 0 }}>
      <LinkBanner />
      <SyncBanner />
      <LoginBanners />
      <SessionBanner />
      <Notices />
    </ScrollView>
  );
}

const s = StyleSheet.create({ stack: { flexGrow: 0, maxHeight: '45%' } });
