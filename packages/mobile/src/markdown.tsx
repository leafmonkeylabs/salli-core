/**
 * An AI's answer drawn from its Markdown (src/lib/markdown.ts) in the
 * brand's type: Geist at body size, bold at its medium weight, code in Geist
 * Mono, lists with their markers hanging. Text only: nothing is linked.
 */
import { Fragment } from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { blocksOfMarkdown, type Span } from './lib/markdown';
import { font, size, useTheme } from './theme';

function Spans({ spans }: { spans: readonly Span[] }) {
  return (
    <>
      {spans.map((span, i) => (
        <Text
          key={i}
          style={[span.bold ? styles.bold : null, span.italic ? styles.italic : null, span.code ? styles.code : null]}
        >
          {span.text}
        </Text>
      ))}
    </>
  );
}

export function Markdown({ text }: { text: string }) {
  const theme = useTheme();
  const colour = { color: theme.text };
  return (
    <View style={{ gap: 10 }}>
      {blocksOfMarkdown(text).map((block, b) => {
        if (block.kind === 'heading') {
          return (
            <Text key={b} accessibilityRole="header" style={[styles.heading, colour]}>
              <Spans spans={block.spans} />
            </Text>
          );
        }
        if (block.kind === 'list') {
          return (
            <View key={b} style={{ gap: 6 }}>
              {block.items.map((item, i) => (
                <View key={i} style={styles.item}>
                  <Text style={[styles.body, styles.marker, { color: theme.muted }]}>{item.marker}</Text>
                  <Text style={[styles.body, colour, { flex: 1 }]}>
                    <Spans spans={item.spans} />
                  </Text>
                </View>
              ))}
            </View>
          );
        }
        return (
          <Text key={b} style={[styles.body, colour]}>
            {block.lines.map((line, l) => (
              <Fragment key={l}>
                {l ? '\n' : null}
                <Spans spans={line} />
              </Fragment>
            ))}
          </Text>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  body: { fontFamily: font.regular, fontSize: size.body, lineHeight: size.body * 1.55 },
  heading: { fontFamily: font.medium, fontSize: size.body, lineHeight: size.body * 1.4, marginTop: 4 },
  bold: { fontFamily: font.medium },
  italic: { fontStyle: 'italic' },
  code: { fontFamily: font.mono, fontSize: size.body - 1 },
  item: { flexDirection: 'row', gap: 8 },
  marker: { minWidth: 16 },
});
