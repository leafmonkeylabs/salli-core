/**
 * @leafmonkeylabs/salli-console: the Salli console, for building an edition
 * of it (decision 19). An edition imports `createConsole` and the kit, adds
 * its extensions, and builds one bundle:
 *
 *     import '@leafmonkeylabs/salli-console/styles.css';
 *     import { createConsole } from '@leafmonkeylabs/salli-console';
 *     createConsole({ extensions: [example] }).mount(document.getElementById('root')!);
 *
 * The kit keeps Salli's rules for any page it builds: amounts through
 * <Money> (decimal strings, never a float), errors as problem details,
 * charts that label every figure with the server's own string.
 */
export { createConsole, type CreateConsoleOptions, type SalliConsole } from './console';
export type { ConsoleExtension, ConsoleRoute, NavigationItem, SettingsPanel, ThemeTokens } from './extensions';
export { TOKEN_NAMES, type TokenName } from './theme';
export { useApi, useRead, useSession, useWrite, type WriteOptions } from './api';
export { isStepUpRequired, type ConsoleSession, type SessionState } from './auth/session';
export { usePreferences, useLocale, type Theme } from './preferences';
export { strings } from './strings';

// The kit.
export { Money, spokenAmount, visibleAmount, type MoneyProps } from './kit/Money';
export { Table, type Column, type TableProps } from './kit/Table';
export { Empty, Grid, Loaded, Loading, Page, Panel, Provenance, Row, Rows, Section } from './kit/layout';
export { Button, Confirm, Field, RadioField, SelectField, TextAreaField, TextField, type ConfirmProps, type FieldProps } from './kit/forms';
export { amountInput, dateInput, nonNegativeAmountInput, positiveAmountInput, rateInput, signedAmountInput, wholeNumberInput } from './kit/inputs';
export { saveText, textOf } from './kit/download';
export { ProblemView } from './kit/Problem';
export { ThinkItThrough } from './kit/ThinkItThrough';
export { Logo } from './kit/Logo';
export { ChartFigure } from './kit/chart/ChartFigure';
export { LineChart, LineKey, type LineChartProps, type LineMark, type LineSeries } from './kit/chart/LineChart';
export { RangeChart, type RangeChartProps } from './kit/chart/RangeChart';
export { DotChart, type DotChartProps, type DotRow } from './kit/chart/DotChart';
export { amountScale, bandScale, extent, indexScale, linePath, spread, stepPath } from './kit/chart/geometry';
export { displayDate, displayMoment, displayMonth, displayRange, isoDate } from './kit/dates';
