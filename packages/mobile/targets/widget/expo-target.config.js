// The widgets (design 15): safe to spend and what is waiting, on the Home
// Screen as white tiles with the container's own 22 point corners and on the lock screen as the system tints them.
// They read the snapshot the app writes (src/glance.tsx) and ask no server.
/** @type {import('@bacons/apple-targets/app.plugin').ConfigFunction} */
module.exports = (config) => ({
  type: 'widget',
  name: 'SalliWidget',
  displayName: 'Salli',
  deploymentTarget: '17.0',
  // The app's v2 roles for the widget's fallback, before the app has written a snapshot: surface, ink, muted, line and green, light and night.
  colors: {
    $accent: { light: '#2E6A55', dark: '#7CC0A5' },
    $widgetBackground: { light: '#FFFFFF', dark: '#171B19' },
    paper: { light: '#FFFFFF', dark: '#171B19' },
    ink: { light: '#18201C', dark: '#ECEFEC' },
    muted: { light: '#5F6661', dark: '#9BA39D' },
    rule: { light: '#ECEBE7', dark: '#262B28' },
    mark: { light: '#2E6A55', dark: '#7CC0A5' },
  },
  entitlements: {
    'com.apple.security.application-groups': config.ios.entitlements['com.apple.security.application-groups'],
  },
});
