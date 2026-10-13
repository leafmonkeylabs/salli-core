/**
 * What the shell and its pages share (C5): the places, and how a page
 * tells the shell its title (and anything between it and its place) for
 * the breadcrumb.
 */
import { createContext, useContext } from 'react';
import type { Crumb, Place } from './places';
import { placesOf } from './places';

export interface ShellPage {
  places: readonly Place[];
  /** A page's title and the crumbs between its place and it. */
  report: (title: string, trail: readonly Crumb[]) => void;
}

const fallback: ShellPage = { places: placesOf([]), report: () => {} };

export const ShellContext = createContext<ShellPage>(fallback);

export function useShellPage(): ShellPage {
  return useContext(ShellContext);
}
