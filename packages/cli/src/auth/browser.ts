/**
 * Opening a URL in the user's browser, with the platform's own command.
 * (No library: the `open` package ships a script it locates on disk, which a
 * single-file executable does not have.)
 */
import { spawn } from 'node:child_process';

interface Launch {
  command: string;
  args: string[];
}

function launchersFor(url: string, env: Record<string, string | undefined>, platform: NodeJS.Platform): Launch[] {
  const browser = env.BROWSER?.trim();
  if (browser) {
    // BROWSER may name a command, or a template with %s for the URL.
    const [command, ...args] = browser.split(/\s+/);
    if (command) {
      const withUrl = args.some((a) => a.includes('%s')) ? args.map((a) => a.replaceAll('%s', url)) : [...args, url];
      return [{ command, args: withUrl }];
    }
  }
  if (platform === 'darwin') return [{ command: 'open', args: [url] }];
  // rundll32 takes the URL as one argument; no shell sees the &s in it.
  if (platform === 'win32') return [{ command: 'rundll32', args: ['url.dll,FileProtocolHandler', url] }];
  return [
    { command: 'xdg-open', args: [url] },
    { command: 'wslview', args: [url] },
    { command: 'sensible-browser', args: [url] },
  ];
}

function tryLaunch(launch: Launch): Promise<boolean> {
  return new Promise((resolve) => {
    try {
      const child = spawn(launch.command, launch.args, { detached: true, stdio: 'ignore' });
      child.once('error', () => resolve(false));
      child.once('spawn', () => {
        child.unref();
        resolve(true);
      });
    } catch {
      resolve(false);
    }
  });
}

/** Opens `url` in a browser. Resolves false when no launcher worked. */
export async function openInBrowser(
  url: string,
  env: Record<string, string | undefined>,
  platform: NodeJS.Platform,
): Promise<boolean> {
  if (!/^https?:\/\//i.test(url)) return false;
  for (const launch of launchersFor(url, env, platform)) {
    if (await tryLaunch(launch)) return true;
  }
  return false;
}

/**
 * Whether a browser can open on this machine, as far as can be told: not in
 * an SSH session or on CI, and on Linux and the BSDs only with a display (or
 * under WSL). BROWSER, when set, is taken at its word.
 */
export function browserAvailable(env: Record<string, string | undefined>, platform: NodeJS.Platform): boolean {
  const set = (name: string): boolean => {
    const value = env[name]?.trim().toLowerCase();
    return !!value && value !== '0' && value !== 'false';
  };
  if (set('BROWSER')) return true;
  if (set('CI') || set('SSH_CONNECTION') || set('SSH_CLIENT') || set('SSH_TTY')) return false;
  if (platform === 'darwin' || platform === 'win32') return true;
  return set('DISPLAY') || set('WAYLAND_DISPLAY') || set('WSL_DISTRO_NAME');
}
