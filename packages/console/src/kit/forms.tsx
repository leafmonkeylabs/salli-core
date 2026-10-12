/**
 * Forms, on React Aria Components (decision 10): labels above the inputs,
 * inputs on bone with a hairline border, the focus ring ledger green (sand
 * on dark), errors in words beside the field. A confirmation says what will
 * happen in Salli's words before a write, in a dialog that traps focus and
 * gives it back.
 *
 * React Aria's press handling would add a <style> to the page, which the
 * CSP refuses; the console's stylesheet carries that rule instead
 * (kit.css, `[data-react-aria-pressable]`) and `createConsole` marks it as
 * present, so React Aria adds nothing.
 */
import { useEffect, useId, useRef, type ReactNode } from 'react';
import {
  Button as AriaButton,
  FieldError,
  Input,
  Label,
  Text,
  TextField as AriaTextField,
  type ButtonProps,
  type TextFieldProps,
} from 'react-aria-components';

export function Button({ variant = 'primary', className, ...props }: ButtonProps & { variant?: 'primary' | 'secondary' | 'tertiary' }) {
  return <AriaButton {...props} className={['button', `button-${variant}`, typeof className === 'string' ? className : ''].filter(Boolean).join(' ')} />;
}

export function TextField({
  label,
  description,
  errorMessage,
  inputProps,
  ...props
}: TextFieldProps & {
  label: string;
  description?: ReactNode;
  errorMessage?: string | ((validation: { validationErrors: string[] }) => string);
  inputProps?: { autoComplete?: string; list?: string; spellCheck?: boolean; placeholder?: string; inputMode?: 'text' | 'decimal' };
}) {
  return (
    <AriaTextField {...props} className="field">
      <Label className="field-label">{label}</Label>
      <Input className="field-input" {...inputProps} />
      {description ? (
        <Text slot="description" className="field-help">
          {description}
        </Text>
      ) : null}
      <FieldError className="field-error">{errorMessage}</FieldError>
    </AriaTextField>
  );
}

export interface ConfirmProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  onConfirm: () => void;
  isPending?: boolean;
}

/**
 * Asks before a write, saying what will happen. The browser's own modal
 * <dialog>: it makes the page behind inert, traps focus, closes on Escape
 * and gives focus back, with no script injecting styles (React Aria's
 * modal does, on iOS, which the CSP refuses).
 */
export function Confirm({ isOpen, onOpenChange, title, children, confirmLabel, cancelLabel, onConfirm, isPending }: ConfirmProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (isOpen && !dialog.open) dialog.showModal();
    if (!isOpen && dialog.open) dialog.close();
  }, [isOpen]);
  return (
    <dialog ref={ref} className="modal dialog" role="alertdialog" aria-labelledby={titleId} onClose={() => onOpenChange(false)}>
      <h2 id={titleId} className="dialog-title">
        {title}
      </h2>
      {isOpen ? (
        <>
          <div className="dialog-body">{children}</div>
          <div className="dialog-actions">
            <Button variant="secondary" autoFocus onPress={() => onOpenChange(false)}>
              {cancelLabel}
            </Button>
            <Button variant="primary" onPress={onConfirm} isPending={isPending ?? false}>
              {confirmLabel}
            </Button>
          </div>
        </>
      ) : null}
    </dialog>
  );
}
