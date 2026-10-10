/**
 * Permissions a sign-in may hold beyond reading and writing your data, as the
 * server names them (src/salli/application/permissions.py).
 */
import type { PersonalAccessToken } from '@leafmonkeylabs/salli-sdk';

export type Permission = PersonalAccessToken['permissions'][number];

/** Activate a tax rule set: make a version the one Salli computes with. */
export const TAX_ACTIVATE: Permission = 'tax:activate';

/** Every permission there is, as the API document lists them. */
export const PERMISSIONS: readonly Permission[] = [TAX_ACTIVATE];
