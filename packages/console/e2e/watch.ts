/**
 * What every browser run checks besides its own assertions: no CSP or
 * Trusted Types violation (reported by the page as it happens), no script
 * error, and no request to any origin but the console's own.
 */
import { expect, type Page } from '@playwright/test';

export interface Watch {
  violations: () => Promise<string[]>;
  errors: string[];
  elsewhere: string[];
  /** Fails the test on anything seen. */
  check: () => Promise<void>;
}

declare global {
  interface Window {
    __salliViolations?: string[];
  }
}

export async function watch(page: Page, origin: string): Promise<Watch> {
  await page.addInitScript(() => {
    window.__salliViolations = [];
    document.addEventListener('securitypolicyviolation', (event) => {
      window.__salliViolations?.push(`${event.effectiveDirective}: ${event.blockedURI || 'inline'} at ${event.sourceFile}:${event.lineNumber} ${event.sample}`);
    });
  });
  const errors: string[] = [];
  const elsewhere: string[] = [];
  page.on('console', (message) => {
    if (message.type() === 'error' && /Content Security Policy|TrustedHTML|TrustedScript|Trusted Type|Refused to/i.test(message.text())) errors.push(message.text());
  });
  page.on('pageerror', (error) => errors.push(`${error.name}: ${error.message}`));
  page.on('request', (request) => {
    const url = new URL(request.url());
    if (!['http:', 'https:'].includes(url.protocol)) return;
    if (url.origin !== origin) elsewhere.push(request.url());
  });
  const violations = async (): Promise<string[]> => {
    try {
      return await page.evaluate(() => window.__salliViolations ?? []);
    } catch {
      return [];
    }
  };
  return {
    violations,
    errors,
    elsewhere,
    check: async () => {
      expect(await violations(), 'CSP violations').toEqual([]);
      expect(errors, 'script errors and CSP reports').toEqual([]);
      expect(elsewhere, 'requests to another origin').toEqual([]);
    },
  };
}
