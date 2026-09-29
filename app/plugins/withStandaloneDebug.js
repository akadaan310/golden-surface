// Makes the debug APK run on its own: the JS bundle is embedded (instead of
// fetched from Metro) and React Native dev support is off, so the app never
// looks for a dev server. Still a debug build: debuggable, debug-signed.
const { withAppBuildGradle, withMainApplication } = require('expo/config-plugins');

module.exports = function withStandaloneDebug(config) {
  config = withAppBuildGradle(config, (c) => {
    const src = c.modResults.contents;
    if (!src.includes('debuggableVariants = []')) {
      c.modResults.contents = src.replace(
        /react \{\n/,
        'react {\n    // golden-surface: embed the JS bundle in debug builds too\n    debuggableVariants = []\n',
      );
    }
    return c;
  });
  config = withMainApplication(config, (c) => {
    const src = c.modResults.contents;
    if (!src.includes('useDevSupport = false')) {
      c.modResults.contents = src.replace(
        /ExpoReactHostFactory\.getDefaultReactHost\(\n(\s*)context = applicationContext,/,
        'ExpoReactHostFactory.getDefaultReactHost(\n$1context = applicationContext,\n$1useDevSupport = false, // golden-surface: never look for Metro',
      );
    }
    return c;
  });
  return config;
};
