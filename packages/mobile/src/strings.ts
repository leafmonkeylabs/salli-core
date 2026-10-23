/**
 * Every word the app shows, in the brand's voice (docs/brand/README.md):
 * British English, sentence case, no exclamation marks, nothing that ranks
 * or urges. Where the console already says a thing, the app says it the same.
 */
export const strings = {
  welcome: {
    title: 'Your books, on your phone.',
    body: 'Connect to the Salli server you run. Your books stay there; this app shows them and adds to them.',
    label: 'Server address',
    placeholder: 'money.example.org',
    help: 'The address you open the console at. The app adds https:// itself.',
    check: 'Check this server',
    notAnAddress: 'That isn’t a server address. Type it as you would in a browser: money.example.org.',
    noServer: 'No server yet? Run one with Docker in three steps',
    noServerUrl: 'https://salli.money/self-host/',
    footer: 'Salli is free and open source. Servers run for you are planned.',
  },

  connect: {
    back: 'Change the address',
    checking: (host: string) => `Checking ${host}…`,
    found: 'Salli server found',
    version: 'Salli',
    api: 'API',
    apiOk: 'v1, which this app speaks',
    connection: 'Connection',
    https: 'HTTPS',
    local: 'This machine',
    signInNote: (host: string) =>
      `You sign in on ${host}'s own page, with the email and password its owner gave you. This app never sees your password.`,
    signIn: (host: string) => `Sign in on ${host}`,
    sheetNote: 'Opens the server’s page in a secure browser sheet, then comes back here.',
    signingIn: 'Signing in…',
    tryAgain: 'Try again',
  },

  problem: {
    unreachableTitle: 'Couldn’t reach Salli',
    unreachable: (origin: string) => `Couldn't reach Salli at ${origin}. Check that the server is running, then try again.`,
    'not-salli': { title: 'No Salli server there', body: (origin: string) => `${origin} answered, but not as a Salli server does. Check the address: it is the one the console opens at, without /console.` },
    version: { title: 'A Salli this app doesn’t speak', body: (origin: string) => `${origin} runs a version of Salli whose API this app doesn't know. Update the app, or the server.` },
    'no-app-sign-in': { title: 'No app sign-in on this server', body: (origin: string) => `${origin} runs a Salli with no sign-in for this app. Upgrade the server, or use the salli command.` },
    insecure: {
      title: 'This server needs HTTPS',
      body: (origin: string) =>
        `${origin} answered over plain HTTP. The app signs in only over HTTPS: a password should only cross a network encrypted. Serve it on your own domain with the tls profile, as docs/self-host.md shows.`,
    },
    deniedTitle: 'Not signed in',
    denied: 'The sign-in page was left without signing in. Nothing was changed.',
    failedTitle: 'Signing in didn’t finish',
    failed: (detail: string) => `${detail} Try again from here.`,
    signedOutTitle: 'Signed out',
    signedOut: 'This sign-in has ended: it was signed out from elsewhere, or its refresh token was used twice, which Salli treats as a sign it was copied.',
    signInAgain: 'Sign in again',
  },

  nav: { home: 'Home', cash: 'Cash', decide: 'Decide', books: 'Books', more: 'More' },

  home: {
    title: 'Home',
    switchServer: (host: string) => `Server: ${host}, signed in. Switch server`,
    add: 'Add an entry',
    safe: 'Safe to spend',
    safeUntil: (date: string, what: string) => `until ${date}, when ${what} comes in.`,
    safeNoIncome: 'No income is expected in the forecast.',
    asOf: (date: string) => `As of ${date}`,
    netWorth: 'Net worth',
    spentIn: (month: string) => `Spent in ${month}`,
    fiScore: (grade: string) => `FI score · ${grade}`,
    placeholders: 'Placeholder assumptions',
    ownAssumptions: 'Your own assumptions',
    attention: 'Needs attention',
    nothingNeedsAttention: 'Nothing needs attention.',
    reviewDue: (date: string) => `Review due ${date}`,
    overdue: (date: string) => `Overdue: due ${date}`,
    due: (date: string) => `Due ${date}`,
    decision: 'A decision is ready for review',
    done: 'Done',
    markDone: (what: string) => `Mark done: ${what}`,
    loading: (what: string) => `Loading ${what}…`,
  },

  later: {
    body: 'This place comes next in the app. Until then it is in the console, on this server.',
    open: 'Open the console',
  },

  more: {
    title: 'More',
    server: 'Signed in to',
    as: (email: string) => `as ${email}`,
    signOut: (host: string) => `Sign out of ${host}`,
    signOutNote: 'Ends this sign-in on the server. Your books stay there.',
    footer: 'Salli for iPhone and Android, free and open source. Your books stay on your server.',
  },
} as const;
