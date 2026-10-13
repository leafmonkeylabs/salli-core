/**
 * What the console shows when it isn't showing a page: starting, on its way
 * to the sign-in page, refusing plain HTTP, unable to reach Salli, signed
 * out (and why), or back from a sign-in that can't be used. Each says what
 * happened, then what to do.
 */
import type { ReactNode } from 'react';
import type { ConsoleSession, SessionState } from '../auth/session';
import { Logo } from '../kit/Logo';
import { ProblemView } from '../kit/Problem';
import { strings } from '../strings';

function Frame({ title, children, busy }: { title: string; children?: ReactNode; busy?: boolean }) {
  return (
    <div className="screen">
      <main className="screen-card" aria-busy={busy ?? false}>
        <div className="screen-logo">
          <Logo />
        </div>
        <h1>{title}</h1>
        {children}
      </main>
    </div>
  );
}

export function Screen({ state, session }: { state: Exclude<SessionState, { status: 'signed-in' }>; session: ConsoleSession }) {
  const signIn = (
    <button type="button" className="button button-primary" onClick={() => void session.signIn()}>
      {strings.signIn.signInAgain}
    </button>
  );
  switch (state.status) {
    case 'starting':
      return (
        <Frame title={strings.start.title} busy>
          <p role="status">{strings.loading}</p>
        </Frame>
      );
    case 'redirecting':
      return (
        <Frame title={strings.signIn.signIn} busy>
          <p role="status">{strings.signIn.redirecting}</p>
        </Frame>
      );
    case 'insecure':
      return (
        <Frame title={strings.start.insecureTitle}>
          <p>{strings.start.insecure(state.origin)}</p>
          <p>{strings.start.insecureFix}</p>
        </Frame>
      );
    case 'unreachable':
      return (
        <Frame title={strings.start.unreachableTitle}>
          <ProblemView error={state.error} compact />
          <button type="button" className="button button-primary" onClick={() => window.location.reload()}>
            {strings.start.retry}
          </button>
        </Frame>
      );
    case 'signed-out':
      return (
        <Frame title={strings.signIn.signedOutTitle}>
          <p role="status">{strings.signIn.reasons[state.reason]}</p>
          {signIn}
        </Frame>
      );
    case 'callback-error':
      return (
        <Frame title={state.kind === 'denied' ? strings.signIn.deniedTitle : strings.signIn.staleTitle}>
          {state.kind === 'stale' ? <p>{strings.signIn.stale}</p> : null}
          {state.kind === 'denied' ? <p>{strings.signIn.denied}</p> : null}
          {state.kind === 'failed' ? <ProblemView error={state.error} compact /> : null}
          {signIn}
        </Frame>
      );
  }
}
