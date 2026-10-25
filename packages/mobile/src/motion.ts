/**
 * The app's motion (docs/design/mobile.md, Motion): a few tokens, each with
 * what it becomes under Reduce Motion (opacity only, never nothing). Motion
 * runs on the UI thread, explains a change of state or place, never bounces
 * and never loops; a figure is never animated through values it isn't.
 * Each screen picks the Reduce Motion form itself (`useReducedMotion`), so
 * that form is marked to run even with the setting on; the full forms keep
 * Reanimated's own ReduceMotion.System, which skips them.
 */
import { Easing, FadeIn, FadeInUp, FadeOut, LinearTransition, ReduceMotion, useReducedMotion, type WithSpringConfig } from 'react-native-reanimated';

export { useReducedMotion };

/** A press: scale 0.98 and opacity 0.85, in 80 ms, back in 120 ms; with Reduce Motion, opacity only. */
export const press = { scale: 0.98, opacity: 0.85, in: 80, out: 120, easing: Easing.out(Easing.quad) } as const;

/** A sheet: presented on a critically damped spring (about 220 ms), dismissed in 180 ms carrying the drag's speed. */
export const sheet = {
  present: { stiffness: 500, damping: 50, mass: 1 } satisfies WithSpringConfig,
  dismiss: 180,
  dismissEasing: Easing.bezier(0.3, 0, 1, 1),
  scrim: 160,
  /** Reduce Motion: the sheet and its scrim fade in place. */
  reduced: 150,
  /** Let go past this share of its height, or faster than this (pt/s), and it closes. */
  threshold: 0.3,
  velocity: 800,
} as const;

/** A row in or out of a list: siblings settle on a spring, the row fades; with Reduce Motion, a fade in place. */
export function listMotion(reduced: boolean) {
  return reduced
    ? { entering: FadeIn.duration(120).reduceMotion(ReduceMotion.Never), exiting: FadeOut.duration(120).reduceMotion(ReduceMotion.Never) }
    : {
        entering: FadeIn.duration(160),
        exiting: FadeOut.duration(120),
        layout: LinearTransition.springify().stiffness(400).damping(40).mass(1),
      };
}

/** A confirmation: it fades and rises 8 px over 200 ms, then holds; with Reduce Motion, a fade over 150 ms. */
export function success(reduced: boolean) {
  return reduced ? FadeIn.duration(150).reduceMotion(ReduceMotion.Never) : FadeInUp.duration(200).withInitialValues({ transform: [{ translateY: 8 }] });
}
