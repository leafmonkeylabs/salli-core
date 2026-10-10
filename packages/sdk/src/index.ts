/**
 * @leafmonkeylabs/salli-sdk — a TypeScript client for the Salli API.
 *
 * The operations are generated from the API's OpenAPI document (one function
 * per operation id: `accounts.list` is `accountsList`); the rest of this
 * package is what every client of them needs:
 *
 * - `createClient` — a server, a bearer token that refreshes itself, and
 *   errors as `SalliApiError` (problem details) or `SalliNetworkError`;
 * - the agent's event stream (`streamAgentChat`, `streamAgentResume`);
 * - signing in (`oauth`): PKCE, device codes, refresh, revocation;
 * - money for display (`formatAmount`): exact, from the decimal strings
 *   the API sends, never through a float.
 */
export * from './generated/sdk.gen';
export type * from './generated/types.gen';
export type { Client as FetchClient } from './generated/client';

export {
  createClient,
  normalizeServerUrl,
  type CallOptions,
  type DataOf,
  type RequestLog,
  type SalliClient,
  type SalliClientOptions,
  type StreamRequest,
  type TokenProvider,
} from './client';
export {
  describeDetail,
  isAbortError,
  isProblemDetails,
  SalliApiError,
  SalliNetworkError,
  SalliOAuthError,
  type ProblemDetails,
  type SalliApiErrorInit,
  type ValidationIssue,
} from './errors';
export {
  amountSign,
  compareAmounts,
  currencyDigits,
  formatAmount,
  formatDecimal,
  formatRatio,
  isAmount,
  isNegativeAmount,
  isZeroAmount,
  negateAmount,
  normalizeAmountInput,
  type DecimalString,
  type FormatAmountOptions,
  type FormatDecimalOptions,
  type FormatRatioOptions,
} from './money';
export { parseEventData, readServerSentEvents, type EventSourceMessage } from './sse';
export {
  parseAgentEvent,
  streamAgentChat,
  streamAgentResume,
  streamStrategyGeneration,
  type AgentApprovalRequest,
  type AgentEvent,
  type AgentStreamOptions,
  type StrategyEvent,
} from './agent';
export { exactValue, parseJsonExact, RAW_JSON, rawJsonOf, reindentJson, toJsonText, withRawJson } from './json';
export * as oauth from './oauth';
// `DeviceAuthorization` and `RegisteredClient` at the top level are the
// server's (generated) shapes; the protocol-level ones, which allow what the
// RFCs leave optional, are `oauth.DeviceAuthorization` and so on.
export type { ClientMetadata, OAuthEndpoints, OAuthTokenProvider, PkcePair, StoredTokens, TokenResponse } from './oauth';

/** The API versions this SDK speaks (`api_version` in `/v1/meta`). */
export const SUPPORTED_API_VERSIONS: readonly string[] = ['1'];
