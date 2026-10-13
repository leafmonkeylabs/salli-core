/**
 * Saving a file on this device: the journal's export, a scenario document.
 * The text is already in the page (the API's answer); it becomes a file in
 * the browser's own downloads, and nothing is sent anywhere. A blob URL
 * needs no inline script and no other origin, so the CSP allows it.
 */
export function saveText(filename: string, text: string, type: string, doc: Document = document): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = doc.createElement('a');
  link.href = url;
  link.download = filename;
  link.rel = 'noopener';
  link.hidden = true;
  doc.body.append(link);
  link.click();
  link.remove();
  // The browser has the file once the click is handled; let the URL go after.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** The text of a read the SDK was asked to hand back as text (`parseAs: 'text'`): Markdown. */
export function textOf(value: unknown): string {
  return typeof value === 'string' ? value : JSON.stringify(value);
}
