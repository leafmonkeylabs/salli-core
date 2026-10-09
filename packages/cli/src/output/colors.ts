/**
 * Whether to colour, decided per stream: never when NO_COLOR is set or
 * --no-color is passed, always with FORCE_COLOR, otherwise only for a
 * terminal (and not TERM=dumb). The `color` setting can force it either way.
 */
import picocolors from 'picocolors';
import type { ColorSetting } from '../config/config';

export type Colors = ReturnType<typeof picocolors.createColors>;

export interface ColorDecision {
  /** false when --no-color was passed. */
  flag: boolean;
  setting: ColorSetting | undefined;
  env: Record<string, string | undefined>;
}

export function shouldColor(stream: { isTTY?: boolean }, decision: ColorDecision): boolean {
  if (!decision.flag) return false;
  if (decision.env.NO_COLOR) return false;
  const force = decision.env.FORCE_COLOR;
  if (force !== undefined && force !== '' && force !== '0' && force !== 'false') return true;
  if (decision.setting === 'never') return false;
  if (decision.setting === 'always') return true;
  return stream.isTTY === true && decision.env.TERM !== 'dumb';
}

export function createColors(enabled: boolean): Colors {
  return picocolors.createColors(enabled);
}
