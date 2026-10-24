/**
 * The automation rules of the server on screen (src/lib/automations.ts),
 * kept in this phone's keychain under that server: they name its accounts,
 * and no server sees them. Forgetting the server forgets them.
 */
import type { Account } from '@leafmonkeylabs/salli-sdk';
import * as SecureStore from 'expo-secure-store';
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Body, Money } from './kit';
import type { AutomationRule, Draft } from './lib/automations';
import { displayDate } from './lib/display';
import { storeKeyOf } from './lib/servers';
import { useSession } from './session';
import { strings } from './strings';
import { useTheme } from './theme';

const t = strings.automations;

export interface Automations {
  /** Undefined until read from the keychain. */
  rules: readonly AutomationRule[] | undefined;
  save(rule: AutomationRule): Promise<void>;
  remove(id: string): Promise<void>;
}

export function useAutomations(): Automations {
  const { session } = useSession();
  const server = session.status === 'signed-in' ? session.server : '';
  const [rules, setRules] = useState<readonly AutomationRule[] | undefined>(undefined);

  useEffect(() => {
    setRules(undefined);
    if (!server) return;
    let live = true;
    void SecureStore.getItemAsync(storeKeyOf(server, 'automations')).then((text) => {
      if (!live) return;
      try {
        setRules(text ? (JSON.parse(text) as AutomationRule[]) : []);
      } catch {
        setRules([]);
      }
    });
    return () => {
      live = false;
    };
  }, [server]);

  const store = useCallback(
    async (next: readonly AutomationRule[]) => {
      setRules(next);
      await SecureStore.setItemAsync(storeKeyOf(server, 'automations'), JSON.stringify(next));
    },
    [server],
  );
  const save = useCallback(
    (rule: AutomationRule) => {
      const now = rules ?? [];
      return store(now.some((r) => r.id === rule.id) ? now.map((r) => (r.id === rule.id ? rule : r)) : [...now, rule]);
    },
    [rules, store],
  );
  const remove = useCallback((id: string) => store((rules ?? []).filter((r) => r.id !== id)), [rules, store]);
  return { rules, save, remove };
}

/** What a rule read, as the server will be sent it. */
export function Drafted({ draft, account }: { draft: Draft; account: Account | undefined }) {
  const theme = useTheme();
  const facts: [string, ReactNode][] = [
    [t.fields.date, <Body key="d">{displayDate(draft.date)}</Body>],
    [t.fields.payee, <Body key="p">{draft.description}</Body>],
    [t.fields.amount, account ? <Money key="a" amount={draft.amount} currency={account.currency} /> : <Body key="a">{draft.amount}</Body>],
    [t.fields.direction, <Body key="w">{draft.credit_flag ? t.in : t.out}</Body>],
    [t.fields.account, <Body key="c">{account?.name ?? ''}</Body>],
    ...(draft.bank_ref ? [[t.fields.ref, <Body key="r">{draft.bank_ref}</Body>] as [string, ReactNode]] : []),
  ];
  return (
    <View>
      {facts.map(([label, value]) => (
        <View key={label} accessible style={[styles.fact, { borderBottomColor: theme.rule }]}>
          <Body small muted style={{ width: 96 }}>
            {label}
          </Body>
          <View style={{ flex: 1, alignItems: 'flex-end' }}>{value}</View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  // Read-only rows: 40 px, as Decide's table.
  fact: { flexDirection: 'row', alignItems: 'center', minHeight: 40, borderBottomWidth: StyleSheet.hairlineWidth, gap: 8 },
});
