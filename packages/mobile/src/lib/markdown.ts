/**
 * The little Markdown an AI's answer uses, read into blocks the agent page
 * draws in the brand's type: paragraphs, headings, bulleted and numbered
 * lists, and bold, italic and code within a line. Anything else (links,
 * tables, quotes) stays as its text: nothing is fetched, nothing is hidden.
 */

export type Span = { text: string; bold?: boolean; italic?: boolean; code?: boolean };

export type MdBlock =
  | { kind: 'paragraph'; lines: Span[][] }
  | { kind: 'heading'; spans: Span[] }
  | { kind: 'list'; ordered: boolean; items: { marker: string; spans: Span[] }[] };

const BULLET = /^\s*[-*•]\s+(.*)$/;
const NUMBERED = /^\s*(\d+)[.)]\s+(.*)$/;
const HEADING = /^\s{0,3}#{1,6}\s+(.*?)\s*#*\s*$/;
const RULE = /^\s*([-*_])(\s*\1){2,}\s*$/;

/** One line's bold (`**x**`, `__x__`), italic (`*x*`, `_x_`) and code (`` `x` ``). */
export function spansOf(line: string): Span[] {
  const spans: Span[] = [];
  const pattern = /(\*\*|__)(.+?)\1|`([^`]+)`|(?<![\w*])\*(?!\s)([^*]+?)\*(?![\w*])|(?<![\w_])_(?!\s)([^_]+?)_(?![\w_])/g;
  let at = 0;
  for (const match of line.matchAll(pattern)) {
    const index = match.index ?? 0;
    if (index > at) spans.push({ text: line.slice(at, index) });
    const [, , strong, code, starItalic, underItalic] = match;
    if (strong !== undefined) spans.push(...spansOf(strong).map((s) => ({ ...s, bold: true })));
    else if (code !== undefined) spans.push({ text: code, code: true });
    else spans.push({ text: starItalic ?? underItalic ?? '', italic: true });
    at = index + match[0].length;
  }
  if (at < line.length) spans.push({ text: line.slice(at) });
  return spans.filter((s) => s.text !== '');
}

export function blocksOfMarkdown(text: string): MdBlock[] {
  const blocks: MdBlock[] = [];
  let paragraph: Span[][] = [];
  const flush = () => {
    if (paragraph.length) blocks.push({ kind: 'paragraph', lines: paragraph });
    paragraph = [];
  };
  for (const raw of text.replace(/\r\n?/g, '\n').split('\n')) {
    const line = raw.trimEnd();
    if (!line.trim() || RULE.test(line)) {
      flush();
      continue;
    }
    const heading = HEADING.exec(line);
    const bullet = BULLET.exec(line);
    const numbered = NUMBERED.exec(line);
    if (heading) {
      flush();
      blocks.push({ kind: 'heading', spans: spansOf(heading[1] ?? '') });
    } else if (bullet || numbered) {
      flush();
      const ordered = Boolean(numbered);
      const item = { marker: numbered ? `${numbered[1]}.` : '•', spans: spansOf((numbered ? numbered[2] : bullet?.[1]) ?? '') };
      const last = blocks[blocks.length - 1];
      if (last && last.kind === 'list' && last.ordered === ordered) last.items.push(item);
      else blocks.push({ kind: 'list', ordered, items: [item] });
    } else {
      // A line under a list item, indented, carries on that item.
      const last = blocks[blocks.length - 1];
      if (!paragraph.length && last && last.kind === 'list' && /^\s{2,}/.test(raw)) {
        const item = last.items[last.items.length - 1];
        if (item) item.spans.push({ text: ' ' }, ...spansOf(line.trim()));
        continue;
      }
      paragraph.push(spansOf(line.trim()));
    }
  }
  flush();
  return blocks;
}
