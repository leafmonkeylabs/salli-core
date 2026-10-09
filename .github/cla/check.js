// The Salli CLA check (.github/workflows/cla.yml).
//
// Everyone who wrote commits in a pull request must have accepted the
// Contributor License Agreement (CLA.md) at its current version. People accept
// it by commenting the sign phrase on a pull request; the bot records that on
// the `cla-signatures` branch, then reports a `cla` commit status and keeps one
// comment on the pull request up to date.
//
// Every run reads all of the pull request's comments, not only the one that
// triggered it. Runs for one pull request queue behind each other and GitHub
// keeps only the newest waiting run, so a signature whose own run was dropped
// is still picked up by the run that replaced it.
//
// This runs with write access on pull requests from forks, so the workflow
// only ever executes this file from the default branch, never contributor code.

'use strict';

const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');

const MARKER = '<!-- salli-cla -->';

function loadConfig(root) {
  const config = JSON.parse(fs.readFileSync(path.join(root, '.github/cla/config.json'), 'utf8'));
  const text = fs.readFileSync(path.join(root, config.document), 'utf8');
  const match = text.match(/^Version:\s*(\d+(?:\.\d+)*)/m);
  if (!match) throw new Error(`${config.document} has no "Version:" line`);
  return {
    ...config,
    version: match[1],
    documentSha256: crypto.createHash('sha256').update(text).digest('hex'),
    allowlist: config.allowlist.map((login) => login.toLowerCase()),
  };
}

function normalise(text) {
  return String(text || '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim()
    .replace(/[.!]+$/, '');
}

function isSignature(body, phrase) {
  return normalise(body) === normalise(phrase);
}

function isRecheck(body) {
  return normalise(body) === 'recheck';
}

// Bots, and the maintainers named in config.json, need no signature.
function isExempt(login, config) {
  if (!login) return false;
  const name = login.toLowerCase();
  return name.endsWith('[bot]') || config.allowlist.includes(name);
}

// Who must have signed: the pull request's author and every commit author.
// A commit whose author email belongs to no GitHub account cannot be matched
// to a signature, so it is reported rather than silently let through.
async function contributors(github, repo, pull) {
  const commits = await github.paginate(github.rest.pulls.listCommits, {
    ...repo,
    pull_number: pull.number,
    per_page: 100,
  });
  const people = new Map([[pull.user.id, pull.user.login]]);
  const unlinked = new Set();
  for (const commit of commits) {
    if (commit.author && commit.author.id) {
      people.set(commit.author.id, commit.author.login);
    } else {
      const who = commit.commit && commit.commit.author;
      unlinked.add(who ? `${who.name} <${who.email}>` : commit.sha);
    }
  }
  return { people, unlinked: [...unlinked] };
}

// When the agreement's text last changed on the default branch. A sign comment
// posted before then was agreeing to an earlier text, so it doesn't count.
async function documentChangedAt(github, repo, config, branch) {
  const { data } = await github.rest.repos.listCommits({
    ...repo,
    sha: branch,
    path: config.document,
    per_page: 1,
  });
  return data.length ? Date.parse(data[0].commit.committer.date) : -Infinity;
}

async function readSignatures(github, repo, config) {
  const { data } = await github.rest.repos.getContent({
    ...repo,
    path: config.signaturesPath,
    ref: config.signaturesBranch,
  });
  return {
    record: JSON.parse(Buffer.from(data.content, 'base64').toString('utf8')),
    sha: data.sha,
  };
}

function hasSigned(record, id, config) {
  return record.signatures.some((s) => s.id === id && s.version === config.version);
}

// Records everyone the pull request needs who has posted the sign phrase on it
// since the agreement last changed, re-reading and retrying if another run
// wrote the signatures file first. Returns the signatures file as it now is.
async function recordSignatures(github, repo, config, pull, people, comments, since) {
  const earliest = new Map();
  for (const comment of comments) {
    const user = comment.user;
    if (!user || !people.has(user.id) || isExempt(user.login, config)) continue;
    if (!isSignature(comment.body, config.signPhrase)) continue;
    const at = Date.parse(comment.created_at);
    if (at < since) continue;
    const seen = earliest.get(user.id);
    if (!seen || at < Date.parse(seen.created_at)) earliest.set(user.id, comment);
  }

  for (let attempt = 0; attempt < 4; attempt += 1) {
    const { record, sha } = await readSignatures(github, repo, config);
    const fresh = [...earliest.values()].filter((c) => !hasSigned(record, c.user.id, config));
    if (!fresh.length) return { record, recorded: [] };
    for (const comment of fresh) {
      record.signatures.push({
        id: comment.user.id,
        login: comment.user.login,
        version: config.version,
        document_sha256: config.documentSha256,
        signed_at: comment.created_at,
        pull_request: pull.number,
        comment_url: comment.html_url,
      });
    }
    const logins = fresh.map((c) => c.user.login);
    try {
      await github.rest.repos.createOrUpdateFileContents({
        ...repo,
        path: config.signaturesPath,
        branch: config.signaturesBranch,
        sha,
        message: `${logins.map((login) => `@${login}`).join(', ')} signed the CLA (version ${config.version}) in #${pull.number}`,
        content: Buffer.from(`${JSON.stringify(record, null, 2)}\n`).toString('base64'),
      });
      return { record, recorded: logins };
    } catch (error) {
      if (error.status !== 409) throw error;
    }
  }
  throw new Error('Could not record signatures: the signatures file kept changing');
}

function evaluate(config, people, unlinked, record) {
  const missing = [...people]
    .filter(([id, login]) => !isExempt(login, config) && !hasSigned(record, id, config))
    .map(([, login]) => login);
  return { missing, unlinked };
}

function waitingComment(config, result, urls) {
  const lines = [
    MARKER,
    '### Contributor License Agreement',
    '',
    `Thanks for contributing to Salli! Before this pull request can be merged, everyone who wrote commits in it needs to accept the [Contributor License Agreement](${urls.document}) (version ${config.version}).`,
    '',
  ];
  if (result.missing.length) {
    lines.push(
      `**Still to sign:** ${result.missing.map((login) => `@${login}`).join(', ')}`,
      '',
      'To sign, read the agreement, then reply to this pull request with exactly:',
      '',
      `> ${config.signPhrase}`,
      '',
      `Contributing on behalf of your employer or another company? It needs the [entity agreement](${urls.entity}) instead: open an issue and we will arrange it.`,
      '',
    );
  }
  if (result.unlinked.length) {
    lines.push(
      "**Commits we can't match to a GitHub account:**",
      ...result.unlinked.map((who) => `- \`${who}\``),
      '',
      'Add that email address to your GitHub account (https://github.com/settings/emails), or re-author the commits, then comment `recheck`.',
      '',
    );
  }
  lines.push(
    `<sub>Signatures are public: the bot records your GitHub account, the date, this pull request and the agreement version on the \`${config.signaturesBranch}\` branch.</sub>`,
  );
  return lines.join('\n');
}

async function report(github, repo, config, pull, result, urls, comments) {
  const ok = result.missing.length === 0 && result.unlinked.length === 0;
  const waitingOn = [
    ...result.missing.map((login) => `@${login}`),
    ...(result.unlinked.length ? ['unmatched commit authors'] : []),
  ].join(', ');
  await github.rest.repos.createCommitStatus({
    ...repo,
    sha: pull.head.sha,
    context: config.statusContext,
    state: ok ? 'success' : 'failure',
    target_url: urls.document,
    description: ok
      ? 'Everyone in this pull request has signed the CLA'
      : `Waiting on: ${waitingOn}`.slice(0, 140),
  });

  // Only the bot's own comment, so a marker pasted into someone else's
  // comment can't make the bot rewrite it.
  const existing = comments.find(
    (c) => c.user && c.user.type === 'Bot' && c.body && c.body.includes(MARKER),
  );
  // Nothing to say when nobody ever needed to sign (maintainers, bots).
  if (ok && !existing) return;
  const body = ok
    ? `${MARKER}\n✅ Everyone in this pull request has signed the Salli CLA (version ${config.version}). Thank you!`
    : waitingComment(config, result, urls);
  if (!existing) {
    await github.rest.issues.createComment({ ...repo, issue_number: pull.number, body });
  } else if (existing.body !== body) {
    await github.rest.issues.updateComment({ ...repo, comment_id: existing.id, body });
  }
}

async function run({ github, context, core, root = process.cwd() }) {
  const config = loadConfig(root);
  const repo = { owner: context.repo.owner, repo: context.repo.repo };
  const defaultBranch = context.payload.repository.default_branch;
  const serverUrl = context.serverUrl || 'https://github.com';
  const base = `${serverUrl}/${repo.owner}/${repo.repo}/blob/${defaultBranch}`;
  const urls = { document: `${base}/${config.document}`, entity: `${base}/CLA-ENTITY.md` };

  let pull;
  let trigger = null;
  if (context.eventName === 'pull_request_target') {
    pull = context.payload.pull_request;
  } else if (context.eventName === 'issue_comment') {
    const { issue, comment } = context.payload;
    if (!issue.pull_request) return null;
    ({ data: pull } = await github.rest.pulls.get({ ...repo, pull_number: issue.number }));
    trigger = comment;
  } else {
    return null;
  }

  const { people, unlinked } = await contributors(github, repo, pull);
  const comments = await github.paginate(github.rest.issues.listComments, {
    ...repo,
    issue_number: pull.number,
    per_page: 100,
  });
  // The comment that started this run, in case the listing doesn't show it yet.
  if (trigger && !comments.some((c) => c.id === trigger.id)) comments.push(trigger);
  const since = await documentChangedAt(github, repo, config, defaultBranch);
  const { record, recorded } = await recordSignatures(
    github,
    repo,
    config,
    pull,
    people,
    comments,
    since,
  );
  for (const login of recorded) core.info(`Recorded @${login}'s signature`);

  const result = evaluate(config, people, unlinked, record);
  await report(github, repo, config, pull, result, urls, comments);
  core.info(
    result.missing.length || result.unlinked.length
      ? `Waiting on: ${[...result.missing, ...result.unlinked].join(', ')}`
      : 'Everyone has signed',
  );
  return result;
}

module.exports = run;
module.exports.internal = { isSignature, isRecheck, isExempt, loadConfig, MARKER };
