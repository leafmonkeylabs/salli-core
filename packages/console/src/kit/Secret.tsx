/**
 * A secret shown once (a personal access token just made): in a read-only
 * field, with **Copy it** through the clipboard API and, where that is
 * refused, the text selected for the keyboard to copy. The value lives only
 * in the caller's state: nothing here writes it to storage, logs it or
 * keeps it once the caller lets it go (**I have copied it**, or leaving the
 * page).
 */
import { useEffect, useId, useRef, useState } from 'react';
import { Button } from './forms';

export interface SecretWords {
  once: string;
  copy: string;
  copied: string;
  copyFailed: string;
  done: string;
}

export function Secret({ label, value, words, onDone }: { label: string; value: string; words: SecretWords; onDone: () => void }) {
  const id = useId();
  const field = useRef<HTMLInputElement>(null);
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle');
  // Shown: the person starts at it.
  useEffect(() => {
    field.current?.focus();
    field.current?.select();
  }, [value]);
  const copy = async (): Promise<void> => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied('copied');
    } catch {
      field.current?.focus();
      field.current?.select();
      setCopied('failed');
    }
  };
  return (
    <div className="secret">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input
        ref={field}
        id={id}
        className="field-input secret-value mono"
        readOnly
        value={value}
        autoComplete="off"
        spellCheck={false}
        aria-describedby={`${id}-once`}
        onFocus={(event) => event.currentTarget.select()}
      />
      <p id={`${id}-once`} className="field-help">
        {words.once}
      </p>
      <div className="form-actions">
        <Button variant="secondary" onPress={() => void copy()}>
          {words.copy}
        </Button>
        <Button variant="tertiary" onPress={onDone}>
          {words.done}
        </Button>
        <p role="status" className="quiet-success">
          {copied === 'copied' ? (
            <>
              <span aria-hidden="true">✓</span> {words.copied}
            </>
          ) : copied === 'failed' ? (
            words.copyFailed
          ) : null}
        </p>
      </div>
    </div>
  );
}
