/**
 * "Think this through with your AI" (decision 18). The console holds no
 * chat: it copies a short prompt naming what is on screen, for the person's
 * own AI client connected to Salli over MCP. Nothing is sent anywhere.
 */
import { useState } from 'react';
import { strings } from '../strings';

type Copied = 'idle' | 'copied' | 'failed';

export function ThinkItThrough({ prompt }: { prompt: string }) {
  const [copied, setCopied] = useState<Copied>('idle');
  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(prompt);
      setCopied('copied');
    } catch {
      setCopied('failed');
    }
  };
  return (
    <div className="think">
      <button type="button" className="button button-secondary" onClick={() => void copy()}>
        <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">
          <rect x="8" y="8" width="12" height="12" />
          <path d="M4 16V4h12" />
        </svg>
        {strings.ai.button}
      </button>
      <p className="provenance">{strings.ai.help}</p>
      <p className="sr-only" role="status">
        {copied === 'copied' ? strings.ai.copied : ''}
      </p>
      {copied === 'copied' ? (
        <p className="quiet-success" aria-hidden="true">
          <span aria-hidden="true">✓</span> {strings.ai.copied}
        </p>
      ) : null}
      {copied === 'failed' ? (
        <div className="think-fallback">
          <p>{strings.ai.failed}</p>
          <textarea readOnly value={prompt} rows={4} aria-label={strings.ai.button} />
        </div>
      ) : null}
    </div>
  );
}
