/**
 * salli completion bash | zsh | fish: a completion script, generated from
 * the command tree itself so it is never out of date.
 */
import type { Command } from '@commander-js/extra-typings';
import type { App } from '../app';
import { OUTPUT_FORMATS } from '../config/config';
import { UsageError } from '../errors';

interface Node {
  path: string;
  description: string;
  children: Array<{ name: string; description: string }>;
  /** `file`: its value is a path, so the shell completes file names. */
  options: Array<{ flag: string; description: string; takesValue: boolean; file: boolean }>;
}

// Commander's own command type is generic; only these members are read here.
interface CommandLike {
  name(): string;
  aliases(): string[];
  description(): string;
  commands: readonly CommandLike[];
  options: ReadonlyArray<{
    flags: string;
    long?: string;
    short?: string;
    description: string;
    required: boolean;
    optional: boolean;
    hidden?: boolean;
  }>;
}

function walk(root: CommandLike): Node[] {
  const nodes: Node[] = [];
  const globals = root.options.filter((o) => !o.hidden && o.long !== '--version');
  const visit = (cmd: CommandLike, path: string): void => {
    const own = cmd === root ? root.options.filter((o) => o.long === '--version') : cmd.options.filter((o) => !o.hidden);
    const options = [...own, ...globals, { flags: '--help', long: '--help', description: 'Show help', required: false, optional: false }]
      .flatMap((o) =>
        [o.long, o.short]
          .filter((f): f is string => !!f)
          .map((flag) => ({
            flag,
            description: o.description,
            takesValue: o.required || o.optional,
            file: /<(file|path)>/.test(o.flags),
          })),
      );
    const visible = cmd.commands.filter((c) => c.name() !== 'help');
    nodes.push({
      path,
      description: cmd.description(),
      children: visible.flatMap((c) => [c.name(), ...c.aliases()].map((name) => ({ name, description: c.description() }))),
      options,
    });
    for (const child of visible) visit(child, path ? `${path} ${child.name()}` : child.name());
  };
  visit(root, '');
  return nodes;
}

/** Every command path, including those reached through an alias. */
function allPaths(root: CommandLike): string[] {
  const paths: string[] = [];
  const visit = (cmd: CommandLike, prefix: string): void => {
    for (const child of cmd.commands) {
      if (child.name() === 'help') continue;
      for (const name of [child.name(), ...child.aliases()]) {
        const path = prefix ? `${prefix} ${name}` : name;
        paths.push(path);
        visit(child, path);
      }
    }
  };
  visit(root, '');
  return paths;
}

/** Maps an alias path to its canonical one, for looking up a node. */
function canonical(root: CommandLike): Map<string, string> {
  const map = new Map<string, string>();
  const visit = (cmd: CommandLike, prefix: string, canonPrefix: string): void => {
    for (const child of cmd.commands) {
      if (child.name() === 'help') continue;
      const canon = canonPrefix ? `${canonPrefix} ${child.name()}` : child.name();
      for (const name of [child.name(), ...child.aliases()]) {
        const path = prefix ? `${prefix} ${name}` : name;
        map.set(path, canon);
        visit(child, path, canon);
      }
    }
  };
  visit(root, '', '');
  return map;
}

const shQuote = (text: string): string => `'${text.replace(/'/g, `'\\''`)}'`;

function bash(root: CommandLike): string {
  const nodes = walk(root);
  const canon = canonical(root);
  const paths = allPaths(root);
  const cases = [...canon.entries()].map(([alias, path]) => {
    const node = nodes.find((n) => n.path === path);
    return { alias, node };
  });
  const top = nodes.find((n) => n.path === '');
  const words = (node: Node | undefined): string =>
    node ? [...node.children.map((c) => c.name), ...node.options.map((o) => o.flag)].join(' ') : '';
  const valueOptions = nodes.flatMap((n) => n.options.filter((o) => o.takesValue && o.flag !== '--output'));
  const fileFlags = [...new Set(valueOptions.filter((o) => o.file).map((o) => o.flag))];
  const valueFlags = [...new Set(valueOptions.filter((o) => !o.file).map((o) => o.flag))].filter((f) => !fileFlags.includes(f));
  return `# bash completion for salli. Install:
#   salli completion bash > ~/.local/share/bash-completion/completions/salli
# or add to ~/.bashrc:  source <(salli completion bash)
_salli() {
  local cur prev salli_path="" w i
  cur="\${COMP_WORDS[COMP_CWORD]}"
  prev="\${COMP_WORDS[COMP_CWORD-1]}"
  case "$prev" in
    --output) COMPREPLY=($(compgen -W ${shQuote(OUTPUT_FORMATS.join(' '))} -- "$cur")); return ;;
    ${fileFlags.join('|') || '--none'}) compopt -o filenames 2>/dev/null; COMPREPLY=($(compgen -f -- "$cur")); return ;;
    ${valueFlags.join('|') || '--none'}) COMPREPLY=(); return ;;
  esac
  for ((i = 1; i < COMP_CWORD; i++)); do
    w="\${COMP_WORDS[i]}"
    [[ "$w" == -* ]] && continue
    case "\${salli_path:+$salli_path }$w" in
      ${paths.map((p) => shQuote(p)).join('|')}) salli_path="\${salli_path:+$salli_path }$w" ;;
    esac
  done
  local words
  case "$salli_path" in
    '') words=${shQuote(words(top))} ;;
${cases.map(({ alias, node }) => `    ${shQuote(alias)}) words=${shQuote(words(node))} ;;`).join('\n')}
  esac
  COMPREPLY=($(compgen -W "$words" -- "$cur"))
}
complete -F _salli salli
`;
}

const zshEscape = (text: string): string => text.replace(/\\/g, '\\\\').replace(/:/g, '\\:').replace(/'/g, `'\\''`);

function zsh(root: CommandLike): string {
  const nodes = walk(root);
  const canon = canonical(root);
  const paths = allPaths(root);
  const entries = (node: Node | undefined): { cmds: string; opts: string } => ({
    cmds: (node?.children ?? []).map((c) => `'${zshEscape(c.name)}:${zshEscape(c.description)}'`).join(' '),
    opts: (node?.options ?? []).map((o) => `'${zshEscape(o.flag)}:${zshEscape(o.description)}'`).join(' '),
  });
  const top = entries(nodes.find((n) => n.path === ''));
  const fileFlags = [...new Set(nodes.flatMap((n) => n.options.filter((o) => o.file).map((o) => o.flag)))];
  return `#compdef salli
# zsh completion for salli. Install:
#   salli completion zsh > "\${fpath[1]}/_salli"   (then restart zsh)
# or add to ~/.zshrc:  source <(salli completion zsh)
_salli() {
  local w salli_path=""
  local -a cmds opts
  for w in \${words[2,CURRENT-1]}; do
    [[ $w == -* ]] && continue
    case "\${salli_path:+$salli_path }$w" in
      (${paths.map((p) => p.replace(/ /g, '\\ ')).join('|')}) salli_path="\${salli_path:+$salli_path }$w" ;;
    esac
  done
  if [[ \${words[CURRENT-1]} == --output ]]; then
    compadd -- ${OUTPUT_FORMATS.join(' ')}
    return
  fi
  if [[ \${words[CURRENT-1]} == (${fileFlags.join('|') || '--none'}) ]]; then
    _files
    return
  fi
  case "$salli_path" in
    ('') cmds=(${top.cmds}); opts=(${top.opts}) ;;
${[...canon.entries()]
  .map(([alias, path]) => {
    const e = entries(nodes.find((n) => n.path === path));
    return `    (${alias.replace(/ /g, '\\ ')}) cmds=(${e.cmds}); opts=(${e.opts}) ;;`;
  })
  .join('\n')}
  esac
  if [[ $PREFIX == -* ]]; then
    _describe -t options 'option' opts
  else
    _describe -t commands 'command' cmds
  fi
}
if [[ $zsh_eval_context[-1] == loadautofunc ]]; then
  _salli "$@"
else
  compdef _salli salli
fi
`;
}

const fishEscape = (text: string): string => text.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

function fish(root: CommandLike): string {
  const nodes = walk(root);
  const canon = canonical(root);
  const lines = [
    '# fish completion for salli. Install:',
    '#   salli completion fish > ~/.config/fish/completions/salli.fish',
    `set -g __salli_paths ${[...canon.keys()].map((p) => `'${fishEscape(p)}'`).join(' ')}`,
    'function __salli_path',
    '  set -l tokens (commandline -opc)',
    '  set -e tokens[1]',
    '  set -l salli_path',
    '  for t in $tokens',
    "    string match -q -- '-*' $t; and continue",
    '    set -l candidate (string join " " $salli_path $t)',
    '    if contains -- $candidate $__salli_paths',
    '      set salli_path $salli_path $t',
    '    end',
    '  end',
    '  string join " " $salli_path',
    'end',
    'complete -c salli -f',
    `complete -c salli -l output -x -a '${OUTPUT_FORMATS.join(' ')}' -d 'Output format'`,
  ];
  const byPath = new Map<string, Node>(nodes.map((n) => [n.path, n]));
  const conditions = new Map<string, string[]>([['', ['']]]);
  for (const [alias, path] of canon) conditions.set(path, [...(conditions.get(path) ?? []), alias]);
  for (const [path, aliases] of conditions) {
    const node = byPath.get(path);
    if (!node) continue;
    const condition = `contains -- (__salli_path) ${aliases.map((a) => `'${fishEscape(a)}'`).join(' ')}`;
    for (const child of node.children) {
      lines.push(`complete -c salli -n "${condition}" -a '${fishEscape(child.name)}' -d '${fishEscape(child.description)}'`);
    }
    for (const option of node.options) {
      if (option.flag === '--output') continue;
      const flag = option.flag.startsWith('--') ? `-l ${option.flag.slice(2)}` : `-s ${option.flag.slice(1)}`;
      const value = option.takesValue ? (option.file ? ' -r -F' : ' -r') : '';
      lines.push(`complete -c salli -n "${condition}" ${flag}${value} -d '${fishEscape(option.description)}'`);
    }
  }
  return `${lines.join('\n')}\n`;
}

export function registerCompletion(program: Command, app: App): void {
  program
    .command('completion')
    .argument('<shell>', 'bash, zsh or fish')
    .description('Print a shell completion script')
    .addHelpText(
      'after',
      `
Install:
  bash  salli completion bash > ~/.local/share/bash-completion/completions/salli
  zsh   salli completion zsh > "\${fpath[1]}/_salli"
  fish  salli completion fish > ~/.config/fish/completions/salli.fish`,
    )
    .action((shell) => {
      const root = program as unknown as CommandLike;
      const scripts: Record<string, (r: CommandLike) => string> = { bash, zsh, fish };
      const generate = scripts[shell];
      if (!generate) throw new UsageError(`Completion is available for bash, zsh and fish (not "${shell}").`);
      app.out.write(generate(root));
    });
}
