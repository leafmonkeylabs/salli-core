import { accountsList, entriesList, formatAmount, type JournalEntry } from '@leafmonkeylabs/salli-sdk';
import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, TextInput, View } from 'react-native';
import { useRead } from '../api';
import { Body, Button, Card, LedgerRow, SectionLabel, Waiting } from '../kit';
import { displayDate, displayDay, monthNameOf } from '../lib/display';
import { Page } from '../shell';
import { amountOf } from '../lib/entries';
import { strings } from '../strings';
import { font, size, useTheme } from '../theme';

const t = strings.entries;
/** Entries shown at once; "Show more" adds as many again. */
const PAGE = 50;

/**
 * Every entry in the books, newest first and by month, as the console's
 * Entries page: narrowed by words in the description (the CLI's
 * `--search`), never computed. Opening one shows its lines.
 */
export default function Entries() {
  const theme = useTheme();
  const entries = useRead('entries.list', entriesList);
  const accounts = useRead('accounts.list', accountsList);
  const [words, setWords] = useState('');
  const [shown, setShown] = useState(PAGE);
  const needle = words.trim().toLowerCase();
  // Newest first, within a day too: the server lists them oldest first, and the sort keeps that order reversed.
  const all = [...(entries.data ?? [])].reverse().sort((a, b) => b.entry_date.localeCompare(a.entry_date));
  const matching = needle ? all.filter((e) => e.description.toLowerCase().includes(needle)) : all;
  const page = matching.slice(0, shown);
  const months = page.reduce<{ month: string; rows: JournalEntry[] }[]>((groups, entry) => {
    const month = entry.entry_date.slice(0, 7);
    const last = groups[groups.length - 1];
    if (last?.month === month) last.rows.push(entry);
    else groups.push({ month, rows: [entry] });
    return groups;
  }, []);
  const currency = accounts.data?.[0]?.currency ?? '';

  return (
    <Page title={t.title} back={{ label: t.back, onPress: () => (router.canGoBack() ? router.back() : router.replace('/books')) }} onRefresh={() => entries.refetch()}>
      <View style={{ gap: 6 }}>
        <TextInput
          value={words}
          onChangeText={(text) => {
            setWords(text);
            setShown(PAGE);
          }}
          placeholder={t.search}
          placeholderTextColor={theme.muted}
          accessibilityLabel={t.search}
          accessibilityHint={t.searchHelp}
          returnKeyType="search"
          autoCapitalize="none"
          autoCorrect={false}
          clearButtonMode="while-editing"
          style={[styles.input, { backgroundColor: theme.input, borderRadius: Math.min(theme.control, 12), borderColor: theme.fieldBorder, color: theme.text }]}
        />
        {entries.data ? (
          <Body small muted>
            {t.shown(page.length, matching.length)}
          </Body>
        ) : null}
      </View>

      {entries.data ? (
        matching.length ? (
          <>
            {months.map(({ month, rows }) => (
              <Card key={month} style={{ paddingVertical: 12 }}>
                <SectionLabel>{`${monthNameOf(`${month}-01`)} ${month.slice(0, 4)}`}</SectionLabel>
                <View style={{ marginTop: 4 }}>
                  {rows.map((entry, i) => {
                    const one = amountOf(entry);
                    const spoken = one ? formatAmount(one.amount, one.currency, { display: 'name' }) : t.lines(entry.postings.length);
                    return (
                      <LedgerRow
                        key={entry.id}
                        lead={displayDay(entry.entry_date)}
                        title={entry.description}
                        {...(one ? { amount: one.amount } : { note: t.lines(entry.postings.length) })}
                        currency={one?.currency ?? currency}
                        label={[displayDate(entry.entry_date), entry.description, spoken, entry.reversed_by ? t.reversed : ''].filter(Boolean).join(', ')}
                        onPress={() => router.push({ pathname: '/entry/[id]', params: { id: entry.id } })}
                        last={i === rows.length - 1}
                      />
                    );
                  })}
                </View>
              </Card>
            ))}
            {matching.length > shown ? <Button kind="secondary" label={t.showMore(Math.min(PAGE, matching.length - shown))} onPress={() => setShown((n) => n + PAGE)} /> : null}
          </>
        ) : (
          <Card>
            <Body muted>{needle ? t.noMatch(words.trim()) : t.none}</Body>
          </Card>
        )
      ) : (
        <Waiting query={entries} what="your entries" />
      )}
    </Page>
  );
}

const styles = StyleSheet.create({
  input: { minHeight: size.target, borderWidth: 1, borderRadius: 0, paddingHorizontal: 14, fontFamily: font.regular, fontSize: size.body },
});
