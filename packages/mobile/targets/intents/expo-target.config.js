// The Shortcuts action (docs/design/mobile.md, "Automations"): "Draft from a
// bank's message" adds the message to a queue in the app group and returns.
// It sends nothing and reads no rule: Salli does both when it next runs.
/** @type {import('@bacons/apple-targets/app.plugin').ConfigFunction} */
module.exports = (config) => ({
  type: 'app-intent',
  name: 'SalliIntents',
  displayName: 'Salli',
  deploymentTarget: '17.0',
  entitlements: {
    'com.apple.security.application-groups': config.ios.entitlements['com.apple.security.application-groups'],
  },
});
