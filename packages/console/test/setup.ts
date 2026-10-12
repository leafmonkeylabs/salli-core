/**
 * What jsdom lacks that the console uses: the modal <dialog>'s showModal
 * and close (the browser's own, in the end-to-end runs).
 */
if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
    if (!this.open) return;
    this.open = false;
    this.dispatchEvent(new Event('close'));
  };
}

// The router restores the scroll position on a new page; jsdom has no layout to scroll.
if (typeof window !== 'undefined') window.scrollTo = () => undefined;
