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
  TextArea,
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
  inputProps?: {
    autoComplete?: string;
    list?: string;
    spellCheck?: boolean;
    placeholder?: string;
    inputMode?: 'text' | 'decimal' | 'numeric';
    min?: string;
    className?: string;
  };
}) {
  const { className: inputClass, ...rest } = inputProps ?? {};
  return (
    <AriaTextField {...props} className="field">
      <Label className="field-label">{label}</Label>
      <Input className={['field-input', inputClass ?? ''].filter(Boolean).join(' ')} {...rest} />
      {description ? (
        <Text slot="description" className="field-help">
          {description}
        </Text>
      ) : null}
      <FieldError className="field-error">{errorMessage}</FieldError>
    </AriaTextField>
  );
}

/**
 * A field's error, as Salli or the form found it: shown beside the field
 * and tied to it, so a screen reader reads it with the field. Every field
 * below takes one (`error`), whichever path it came from.
 */
export interface FieldProps {
  label: string;
  description?: ReactNode;
  error?: string | undefined;
  isRequired?: boolean;
}

/** A text field whose error is the caller's: Salli's, at its path, or the form's own. */
export function Field({
  label,
  description,
  error,
  isRequired,
  value,
  onChange,
  type,
  inputProps,
  name,
}: FieldProps & {
  value: string;
  onChange: (value: string) => void;
  type?: 'text' | 'date' | 'password';
  name?: string;
  inputProps?: { inputMode?: 'text' | 'decimal' | 'numeric'; placeholder?: string; min?: string; spellCheck?: boolean; autoComplete?: string; className?: string; list?: string };
}) {
  return (
    <TextField
      label={label}
      description={description}
      value={value}
      onChange={onChange}
      isRequired={isRequired ?? false}
      isInvalid={Boolean(error)}
      errorMessage={error ?? ''}
      validationBehavior="aria"
      {...(type ? { type } : {})}
      {...(name ? { name } : {})}
      inputProps={{ autoComplete: 'off', ...inputProps }}
    />
  );
}

/** Words of the person's own, over several lines: their reasons, a note, a reflection. */
export function TextAreaField({
  label,
  description,
  error,
  isRequired,
  value,
  onChange,
  rows = 4,
}: FieldProps & { value: string; onChange: (value: string) => void; rows?: number }) {
  return (
    <AriaTextField
      className="field"
      value={value}
      onChange={onChange}
      isRequired={isRequired ?? false}
      isInvalid={Boolean(error)}
      validationBehavior="aria"
    >
      <Label className="field-label">{label}</Label>
      <TextArea className="field-input field-textarea" rows={rows} />
      {description ? (
        <Text slot="description" className="field-help">
          {description}
        </Text>
      ) : null}
      <FieldError className="field-error">{error ?? ''}</FieldError>
    </AriaTextField>
  );
}

/** One of a few, as the browser's own <select>: an account, a debt, a cadence. */
export function SelectField({
  label,
  description,
  error,
  isRequired,
  value,
  onChange,
  options,
}: FieldProps & { value: string; onChange: (value: string) => void; options: ReadonlyArray<{ value: string; label: string }> }) {
  const id = useId();
  const help = `${id}-help`;
  const err = `${id}-error`;
  const described = [description ? help : '', error ? err : ''].filter(Boolean).join(' ');
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <select
        id={id}
        className="field-input field-select"
        value={value}
        onChange={(event) => onChange(event.currentTarget.value)}
        required={isRequired ?? false}
        aria-invalid={error ? true : undefined}
        aria-describedby={described || undefined}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {description ? (
        <p id={help} className="field-help">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={err} className="field-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** One of two to five, as radio buttons in a group with its question as the legend. */
export function RadioField({
  label,
  description,
  error,
  isRequired,
  value,
  onChange,
  options,
}: FieldProps & { value: string; onChange: (value: string) => void; options: ReadonlyArray<{ value: string; label: string }> }) {
  const id = useId();
  const help = `${id}-help`;
  const err = `${id}-error`;
  const described = [description ? help : '', error ? err : ''].filter(Boolean).join(' ');
  return (
    <fieldset className="field choices-field" aria-describedby={described || undefined} aria-invalid={error ? true : undefined}>
      <legend className="field-label">{label}</legend>
      <div className="choices">
        {options.map((option) => (
          <label key={option.value} className="choice">
            <input
              type="radio"
              name={id}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              required={isRequired ?? false}
            />
            <span>{option.label}</span>
          </label>
        ))}
      </div>
      {description ? (
        <p id={help} className="field-help">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={err} className="field-error">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}

/**
 * A file from this device, as the browser's own file input (no script
 * reads the disk; the CSP has nothing to refuse). The chosen file is the
 * caller's; `accept` hints which kinds, and the server decides.
 */
export function FileField({
  label,
  description,
  error,
  isRequired,
  accept,
  onChange,
}: FieldProps & { accept?: string; onChange: (file: File | undefined) => void }) {
  const id = useId();
  const help = `${id}-help`;
  const err = `${id}-error`;
  const described = [description ? help : '', error ? err : ''].filter(Boolean).join(' ');
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        type="file"
        className="field-input field-file"
        {...(accept ? { accept } : {})}
        required={isRequired ?? false}
        aria-invalid={error ? true : undefined}
        aria-describedby={described || undefined}
        onChange={(event) => onChange(event.currentTarget.files?.[0] ?? undefined)}
      />
      {description ? (
        <p id={help} className="field-help">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={err} className="field-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/** Yes or no, as the browser's own checkbox, its label beside it. */
export function CheckboxField({
  label,
  description,
  error,
  checked,
  onChange,
}: FieldProps & { checked: boolean; onChange: (checked: boolean) => void }) {
  const id = useId();
  const help = `${id}-help`;
  const err = `${id}-error`;
  const described = [description ? help : '', error ? err : ''].filter(Boolean).join(' ');
  return (
    <div className="field field-check">
      <label className="choice" htmlFor={id}>
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.currentTarget.checked)}
          aria-invalid={error ? true : undefined}
          aria-describedby={described || undefined}
        />
        <span>{label}</span>
      </label>
      {description ? (
        <p id={help} className="field-help">
          {description}
        </p>
      ) : null}
      {error ? (
        <p id={err} className="field-error">
          {error}
        </p>
      ) : null}
    </div>
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
  /** Until what the write needs is filled in (a reason, say). */
  isDisabled?: boolean;
}

/**
 * Asks before a write, saying what will happen. The browser's own modal
 * <dialog>: it makes the page behind inert, traps focus, closes on Escape
 * and gives focus back, with no script injecting styles (React Aria's
 * modal does, on iOS, which the CSP refuses).
 */
export function Confirm({ isOpen, onOpenChange, title, children, confirmLabel, cancelLabel, onConfirm, isPending, isDisabled }: ConfirmProps) {
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
            <Button variant="primary" onPress={onConfirm} isPending={isPending ?? false} isDisabled={isDisabled ?? false}>
              {confirmLabel}
            </Button>
          </div>
        </>
      ) : null}
    </dialog>
  );
}
