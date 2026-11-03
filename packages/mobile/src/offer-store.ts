/**
 * A server's offer, announced from the request layer (session.tsx) to the
 * sheet that shows it (offer.tsx): a refusal that carries one is shown once
 * whichever screen made the call.
 */
import type { Offer } from '@leafmonkeylabs/salli-sdk';

export interface Offered {
  server: string;
  offer: Offer;
}

let listener: ((offered: Offered) => void) | undefined;

export function announceOffer(server: string, offer: Offer): void {
  listener?.({ server, offer });
}

/** The sheet's subscription; returns its end. */
export function onOffer(next: (offered: Offered) => void): () => void {
  listener = next;
  return () => {
    if (listener === next) listener = undefined;
  };
}
