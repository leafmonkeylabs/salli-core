/**
 * Every word the console shows, in one catalogue (decision 13): British
 * English in v1, so a translation can follow by replacing this module.
 *
 * The voice is the brand's (docs/brand/README.md, "Voice"): the true thing
 * plainly, the number first, cite sources, no hype, no exclamation marks,
 * and nothing that ranks (test/strings.test.ts holds every string to it).
 */

export const strings = {
  product: 'Salli',
  skipToContent: 'Skip to the page',
  loading: 'Loading…',
  loadingWhat: (what: string) => `Loading ${what}…`,
  unavailable: 'Unavailable',
  notSet: 'Not set',
  dismiss: 'Dismiss',

  nav: {
    label: 'Places',
    home: 'Home',
    cash: 'Cash',
    decide: 'Decide',
    books: 'Books',
    tax: 'Tax',
    attention: 'Attention',
    fi: 'Independence',
    settings: 'Settings',
    more: 'More',
    signOut: 'Sign out',
    signedInAs: (email: string) => `Signed in as ${email}`,
    // A place's own places, in the side menu and on its pages.
    accounts: 'Accounts',
    entries: 'Entries',
    imports: 'Imports',
    rules: 'Rules',
    overview: 'Overview',
    templates: 'Templates',
    scenarios: 'Scenarios',
    principles: 'Principles',
    journal: 'Journal',
    baseline: 'Baseline',
  },

  shell: {
    showSide: 'Show the side menu',
    hideSide: 'Hide the side menu',
    breadcrumb: 'Where you are',
    backTo: (place: string) => `Back to ${place}`,
    server: (host: string, version: string) => `Server ${host}, Salli ${version}`,
    useDark: 'Use the dark theme',
    useLight: 'Use the light theme',
    you: 'You',
    youAre: (name: string, email: string) => `${name}, signed in as ${email}`,
    foot: 'Self-hosted · AGPL-3.0',
    signals: (n: number) => (n === 1 ? '1 signal' : `${n} signals`),
  },

  pager: {
    showing: (from: number, to: number, of: string) => `Showing ${from}–${to} of ${of}`,
    rows: 'Rows per page',
    page: (page: number, pages: number) => `Page ${page} of ${pages}`,
    previous: 'Previous page',
    next: 'Next page',
  },

  sheet: {
    close: 'Close',
  },

  chips: {
    wholeId: 'the whole id',
  },

  update: {
    message: 'Salli was updated. Reload to continue.',
    reload: 'Reload',
  },

  start: {
    title: 'Opening the console',
    insecureTitle: 'The console needs HTTPS',
    insecure: (origin: string) =>
      `This page was opened over plain HTTP at ${origin}. Browsers allow the sign-in's cryptography only over HTTPS or on this computer (localhost), and a password should only cross a network encrypted.`,
    insecureFix:
      "Open the console at https:// on your own domain (the tls profile in docs/self-host.md), or at http://localhost on the server's own machine.",
    unreachableTitle: "Couldn't reach Salli",
    retry: 'Try again',
    noConsoleClient: 'This server has no console sign-in. Upgrade the server, or use the salli command.',
  },

  signIn: {
    signIn: 'Sign in',
    signInAgain: 'Sign in again',
    redirecting: 'Taking you to Salli’s sign-in page…',
    callbackTitle: 'Signing you in',
    staleTitle: 'That sign-in can’t be used',
    stale: 'It was started in another tab, or has already been used. Sign in again from here.',
    deniedTitle: 'Not signed in',
    denied: 'The sign-in page was left without signing in.',
    signedOutTitle: 'Signed out',
    reasons: {
      'signed-out': 'You signed out. Nothing about this sign-in is kept in this tab.',
      idle: 'You were signed out after 30 minutes without a key or a click, in case this screen is shared.',
      ended:
        'This sign-in has ended: it was signed out from elsewhere, it reached its 12 hours, or its refresh token was used twice, which Salli treats as a sign it was copied.',
    },
    differentPerson: (email: string) =>
      `That was a different account, so nothing was changed. You are still signed in as ${email}.`,
    stepUpCancelled: 'Nothing was changed: the password was not entered again.',
    stepUpAgain:
      'Salli still asks for your password before this. Try again in a moment, or use the salli command.',
  },

  problem: {
    title: "The console hit an error it didn't expect",
    unexpected: (withRequest: boolean) => (withRequest ? 'Reload the page; if it happens again, quote the request below.' : 'Reload the page.'),
    // An untyped problem's title by its status, in place of the HTTP reason phrase.
    byStatus: {
      400: "Salli didn't do this",
      404: 'Not found',
      409: 'Not possible right now',
      422: "Salli couldn't use what was sent",
    } as Record<number, string>,
    network: (origin: string) => `Couldn't reach Salli at ${origin}. Check that the server is running, then try again.`,
    requestId: (id: string) => `Request ${id}. Quote it if you report this.`,
    fields: 'What to change',
    retry: 'Try again',
  },

  money: {
    minus: 'minus',
    plus: 'plus',
  },

  chart: {
    showFigures: 'Show the figures',
    hideFigures: 'Hide the figures',
  },

  ai: {
    button: 'Copy a prompt for your AI',
    prompt: 'The prompt for your AI',
    copied: 'Copied. Paste it into your AI client, connected to Salli over MCP.',
    failed: "Couldn't copy here. Select the text below and copy it.",
    help: 'Nothing is sent from the console: it copies a prompt for the AI you already use.',
  },

  home: {
    title: 'Home',
    description: 'Where you stand today, as salli status shows it.',
    netWorth: 'Net worth',
    assets: 'Assets',
    liabilities: 'Liabilities',
    asOfToday: (date: string) => `As of ${date}, from your ledger`,
    safeToSpend: 'Free until payday',
    safeUntil: (date: string) => `until ${date}`,
    cashToday: 'Cash today',
    nextIncome: 'Next income',
    committed: 'Committed before then',
    nothingCommitted: 'Nothing committed before then.',
    rate: (currency: string, rate: string, source: string, date: string) =>
      `${currency} at ${rate}, ${source}, ${date}`,
    thisMonth: (month: string) => `${month} so far`,
    thisMonthRange: (range: string) => range,
    income: 'Income',
    spending: 'Spending',
    netIncome: 'Net income',
    mostOn: 'Most spent on',
    nothingThisMonth: 'Nothing recorded yet this month.',
    fi: 'Financial independence',
    fiScore: 'FI score',
    fiGrade: (grade: string) => grade,
    fiTooSoon: 'Needs two months of data',
    fiProgress: (share: string) => `${share} of the way to financial independence`,
    savingsRate: 'Savings rate',
    savingsRateOf: (share: string) => `${share} of income`,
    fiBy: 'FI by',
    placeholders: 'Placeholder assumptions.',
    setOwn: 'Set your own on Independence',
    ownAssumptions: 'Your own assumptions.',
    fiScoreAsOf: (date: string) => `Computed by Salli as of ${date}.`,
    attention: 'Needs attention',
    nothingNeedsAttention: 'Nothing needs attention.',
    comingUp: 'Coming up',
    nothingDue: 'Nothing due.',
    overdue: 'Overdue',
    reviews: 'Decisions to review',
    noReviews: 'No decision is due for review.',
    reviewDue: (date: string) => `Review due ${date}`,
    netWorthOverTime: 'Net worth over time',
    netWorthCaption: (latest: string, month: string) =>
      `Net worth at the end of each month, and this month so far: ${latest} in ${month}. What you own is above the line, what you owe below it.`,
    netWorthEmpty: 'No month has ended since your books began.',
    month: 'Month',
    asOf: (date: string) => `As of ${date}`,
    thinkDecision: 'Open the decision lab',
    safeLines: 'Free until payday, line by line',
    safeTotal: 'Free until payday',
    lessEveryday: 'Less everyday spending until then',
    lessCushion: 'Less a cushion: a tenth of a usual month',
    lessGoals: 'Less cash set aside for goals',
    spentIn: (month: string) => `Spent in ${month}`,
    nothingSpent: 'Nothing spent yet this month.',
    incomeAndSpending: (income: string, spending: string) => `Income ${income} · spending ${spending}`,
    fiParts: 'What the FI score is made of',
    fiMore: 'Financial independence, in full',
    fiNote: (grade: string) => `FI score · ${grade}`,
    noticed: 'What Salli noticed',
    review: 'Review',
    due: (date: string) => `Due ${date}`,
    pickMonth: 'Month shown',
    // What each part says while it loads: "Loading net worth…".
    loads: {
      netWorth: 'net worth',
      safeToSpend: 'free until payday',
      month: 'this month',
      fi: 'the FI score',
      netWorthOverTime: 'net worth by month',
      noticed: 'what Salli noticed',
      comingUp: 'what is coming up',
      reviews: 'decisions to review',
      spending: 'spending',
    },
    severity: { high: 'High', medium: 'Medium', low: 'Low', info: 'For information' } as Record<string, string>,
    prompt: (date: string) =>
      [
        `Using my Salli tools, go through where I stand as of ${date}: net worth, safe to spend until my next income, this month so far, my FI score and date, what needs attention, what is coming up and any decision due for review.`,
        'Quote Salli’s figures exactly with their currency, and never compute a figure yourself.',
        'Say which figures rest on placeholder assumptions. Don’t rank anything, and don’t record or change anything without asking me first.',
      ].join(' '),
  },

  settings: {
    places: {
      label: 'Settings',
      profile: 'Profile and sign-ins',
      tokens: 'Tokens',
      ai: 'AI connections',
      digests: 'Digests',
      data: 'Your data',
    },
    title: 'Settings',
    description: 'Your profile, where you are signed in, and how this device shows Salli. Tokens, AI connections, digests and your data are in their own places.',
    profile: 'Profile',
    profileHelp: 'What Salli knows about you. Your tax residency decides whose tax rules compute your tax.',
    email: 'Email',
    displayName: 'Name',
    baseCurrency: 'Base currency',
    baseCurrencyHelp: 'The ISO code your books are kept in. It can change only while nothing is stored in it.',
    taxResidency: 'Tax residency',
    taxResidencyHelp: 'An ISO 3166-1 country code, such as NZ. Salli never infers it.',
    timeZone: 'Time zone',
    timeZoneHelp: 'An IANA name, such as Europe/Lisbon: when your digests go out.',
    save: 'Save the profile',
    saving: 'Saving…',
    saved: 'Saved.',
    invalidCurrency: 'A currency is three letters, such as EUR.',
    invalidCountry: 'A country is two letters, such as NZ.',
    signIns: 'Sign-ins',
    signInsHelp:
      'Every way you are signed in: sessions, the salli command on each machine, the console in each tab. AI connections and tokens have pages of their own.',
    password:
      'Your password is changed with salli password. The console never asks for it: it is typed only on Salli’s own sign-in page and into the salli command.',
    kind: { session: 'Session', cli: 'salli command', console: 'Console', mobile: 'Salli app', app: 'Application' } as Record<string, string>,
    started: 'Started',
    lastUsed: 'Last used',
    ends: 'Ends',
    never: 'Not yet',
    noEnd: 'When revoked',
    thisOne: 'This tab',
    what: 'Sign-in',
    end: 'Sign out',
    endLabel: (what: string, started: string) => `Sign out ${what}, started ${started}`,
    confirmEndTitle: 'Sign out this sign-in?',
    confirmEnd: (what: string, started: string) =>
      `Salli will end the ${what} sign-in started ${started}. Whatever used it will have to sign in again.`,
    confirmEndThis: 'This is the tab you are using: Salli will sign you out here.',
    cancel: 'Cancel',
    ended: 'Signed out.',
    noSignIns: 'No other sign-ins.',
    device: 'On this device',
    deviceHelp: 'Kept in this browser only, never sent to Salli.',
    theme: 'Theme',
    themes: { system: 'As the system', light: 'Light', dark: 'Dark' } as Record<string, string>,
    locale: 'Numbers and dates',
    localeHelp: (example: string) => `As this browser formats them unless you choose a locale, such as en-GB. Now: ${example}`,
    localeInvalid: 'Not a locale this browser knows.',
    localeSave: 'Use this locale',
    localeReset: 'Use the browser’s',
  },

  more: {
    title: 'More',
    description: 'The places that don’t fit on a phone’s bar.',
    places: {
      '/tax': 'Your tax, the rules that compute it, and activating a new version.',
      '/attention': 'What Salli has noticed, and your reminders by due date.',
      '/fi': 'Your FI number, how far along you are, and the assumptions behind it.',
      '/settings': 'Your profile and sign-ins, tokens, AI connections, digests and your data.',
    } as Record<string, string>,
  },

  notFound: {
    title: 'No such page',
    body: 'The console has no page at this address.',
    home: 'Go to Home',
  },
} as const;

export type Strings = typeof strings;
