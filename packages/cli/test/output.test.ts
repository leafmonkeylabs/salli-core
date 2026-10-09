import { describe, expect, it } from 'vitest';
import { createColors, shouldColor } from '../src/output/colors';
import { toCsv } from '../src/output/output';
import { renderDetails, renderTable } from '../src/output/table';
import { displayWidth, sanitize, singleLine, truncate } from '../src/output/text';

const plain = createColors(false);

describe('renderTable', () => {
  const rows = [
    { name: 'Cash', amount: '250.00', note: 'Wallet and petty cash for the office' },
    { name: 'Checking', amount: '12,784.50', note: 'Main account' },
  ];
  const columns = [
    { header: 'NAME', get: (r: (typeof rows)[number]) => r.name },
    { header: 'BALANCE', get: (r: (typeof rows)[number]) => r.amount, align: 'right' as const },
    { header: 'NOTE', get: (r: (typeof rows)[number]) => r.note, shrink: true },
  ];

  it('aligns columns two spaces apart, amounts to the right', () => {
    expect(renderTable(rows, columns, { width: Number.POSITIVE_INFINITY, colors: plain })).toBe(
      [
        'NAME        BALANCE  NOTE',
        'Cash         250.00  Wallet and petty cash for the office',
        'Checking  12,784.50  Main account',
      ].join('\n'),
    );
  });

  it('shrinks the text column to fit the terminal', () => {
    const table = renderTable(rows, columns, { width: 40, colors: plain });
    for (const line of table.split('\n')) expect(displayWidth(line)).toBeLessThanOrEqual(40);
    expect(table).toContain('Wallet and petty c…');
  });

  it('never cuts a column that may not shrink', () => {
    const table = renderTable(rows, columns, { width: 10, colors: plain });
    expect(table).toContain('12,784.50');
  });

  it('keeps hostile text from reaching the terminal', () => {
    const table = renderTable([{ name: 'Evil\u001b[2J\u001b]0;pwned\u0007 name\nwith newline' }], [{ header: 'NAME', get: (r) => r.name }], {
      width: Number.POSITIVE_INFINITY,
      colors: plain,
    });
    expect(table).toBe('NAME\nEvil name with newline');
  });
});

describe('text helpers', () => {
  it('strips escape sequences and controls but keeps text', () => {
    expect(sanitize('a\u001b[31mred\u001b[0m b\u0007c\td')).toBe('ared bc\td');
    expect(singleLine('  two\n lines \r\n')).toBe('two lines');
  });

  it('measures and cuts wide characters by columns', () => {
    expect(displayWidth('日本')).toBe(4);
    expect(truncate('日本語のテキスト', 7)).toBe('日本語…');
    expect(truncate('short', 10)).toBe('short');
  });
});

describe('renderDetails', () => {
  it('aligns labels and leaves out empty values', () => {
    expect(
      renderDetails(
        [
          ['Name', 'Cash'],
          ['Balance', 'USD 250.00'],
          ['Parent', null],
          false,
        ],
        plain,
      ),
    ).toBe('Name     Cash\nBalance  USD 250.00');
  });
});

describe('toCsv', () => {
  it('writes one row per record, quoting where RFC 4180 needs it', () => {
    expect(
      toCsv([
        { id: '1', description: 'Lunch, with "Ada"', amount: '12.50', tags: { category: 'food' } },
        { id: '2', description: 'Rent', amount: '1800.00', reversed_by: null },
      ]),
    ).toBe(
      'id,description,amount,tags,reversed_by\r\n' +
        '1,"Lunch, with ""Ada""",12.50,"{""category"":""food""}",\r\n' +
        '2,Rent,1800.00,,\r\n',
    );
  });
});

describe('shouldColor', () => {
  const tty = { isTTY: true };
  const pipe = { isTTY: false };
  it('colours a terminal, not a pipe', () => {
    expect(shouldColor(tty, { flag: true, setting: undefined, env: {} })).toBe(true);
    expect(shouldColor(pipe, { flag: true, setting: undefined, env: {} })).toBe(false);
  });
  it('honours NO_COLOR, --no-color, FORCE_COLOR, TERM=dumb and the setting', () => {
    expect(shouldColor(tty, { flag: true, setting: undefined, env: { NO_COLOR: '1' } })).toBe(false);
    expect(shouldColor(tty, { flag: false, setting: undefined, env: {} })).toBe(false);
    expect(shouldColor(pipe, { flag: true, setting: undefined, env: { FORCE_COLOR: '1' } })).toBe(true);
    expect(shouldColor(tty, { flag: true, setting: undefined, env: { TERM: 'dumb' } })).toBe(false);
    expect(shouldColor(tty, { flag: true, setting: 'never', env: {} })).toBe(false);
    expect(shouldColor(pipe, { flag: true, setting: 'always', env: {} })).toBe(true);
    // NO_COLOR wins over the setting.
    expect(shouldColor(tty, { flag: true, setting: 'always', env: { NO_COLOR: '1' } })).toBe(false);
  });
});
