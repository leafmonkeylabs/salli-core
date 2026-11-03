/**
 * salli panels list | show: the screens an extension adds to the apps, read
 * as text (docs/design/panels.md). The CLI only reads them: what a panel's
 * actions do is the extension's own API.
 */
import type { Command } from '@commander-js/extra-typings';
import { panelsList, panelsShow } from '@leafmonkeylabs/salli-sdk';
import type { App } from '../app';
import { singleLine } from '../output/text';

export function registerPanels(program: Command, app: App): void {
  const panels = program
    .command('panels')
    .description("Screens this server's extension adds to the apps (none on a plain Salli)")
    .addHelpText(
      'after',
      `
Examples:
  $ salli panels list
  $ salli panels show <id>`,
    );

  panels
    .command('list')
    .alias('ls')
    .description('The screens this server adds')
    .action(async () => {
      const api = await app.api();
      const listed = await api.call(panelsList);
      app.out.emit(listed, {
        human: (d) => {
          if (!d.panels.length) return app.out.note('This server adds no screens.');
          const c = app.out.colors;
          app.out.line(
            app.out.table(d.panels, [
              { header: 'ID', get: (p) => p.id, style: (s) => c.dim(s) },
              { header: 'TITLE', get: (p) => p.title, shrink: true },
              { header: 'LISTED IN', get: (p) => p.entry ?? '—' },
            ]),
          );
        },
      });
    });

  panels
    .command('show')
    .argument('<id>', 'The panel id')
    .description('Show one screen, as the apps would')
    .action(async (id) => {
      const api = await app.api();
      const panel = await api.call(panelsShow, { path: { panel_id: id } });
      app.out.emit(panel, {
        human: (p) => {
          const c = app.out.colors;
          app.out.line(c.bold(singleLine(p.title)));
          for (const section of p.sections) {
            app.out.line('');
            if (section.heading) app.out.line(c.bold(singleLine(section.heading)));
            for (const row of section.rows) {
              if (row.kind === 'text') app.out.line(`  ${singleLine(row.label)}${row.value ? `  ${singleLine(row.value)}` : ''}`);
              else if (row.kind === 'link') app.out.line(`  ${singleLine(row.label)}  ${row.url}`);
              else if (row.kind === 'action') app.out.line(`  [${singleLine(row.label)}]  ${row.action.method} ${row.action.path}`);
              else app.out.line(`  [${singleLine(row.label)}]  form: ${row.fields.map((f) => f.name).join(', ')} -> ${row.submit.path}`);
            }
            if (section.footnote) app.out.line(c.dim(singleLine(section.footnote)));
          }
          if (p.note) app.out.line(`\n${c.dim(singleLine(p.note))}`);
        },
      });
    });
}
