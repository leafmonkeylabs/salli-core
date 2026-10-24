// The widgets (design 15): safe to spend and what is waiting, on the Home
// Screen as paper tiles and on the lock screen as the system tints them.
// They read the snapshot the app writes (src/glance.tsx) and ask no server.
/** @type {import('@bacons/apple-targets/app.plugin').ConfigFunction} */
module.exports = (config) => ({
  type: 'widget',
  name: 'SalliWidget',
  displayName: 'Salli',
  deploymentTarget: '17.0',
  colors: {
    $accent: { light: '#173B33', dark: '#CDBF9F' },
    $widgetBackground: { light: '#F6F3EC', dark: '#0F2924' },
    paper: { light: '#F6F3EC', dark: '#0F2924' },
    ink: { light: '#1C1B19', dark: '#F2ECDF' },
    muted: { light: '#57524A', dark: '#9AAAA2' },
    rule: { light: '#DCD4C4', dark: '#334842' },
    mark: { light: '#173B33', dark: '#CDBF9F' },
  },
  entitlements: {
    'com.apple.security.application-groups': config.ios.entitlements['com.apple.security.application-groups'],
  },
});
