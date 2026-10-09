// Tests for the CLA check, against an in-memory stand-in for the GitHub API.
// Run with: node --test .github/cla/check.test.js

'use strict';

const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const run = require('./check.js');

const { isSignature, isRecheck, MARKER, loadConfig } = run.internal;

const ROOT = path.resolve(__dirname, '../..');
const CONFIG = loadConfig(ROOT);
const PHRASE = CONFIG.signPhrase;

const MAINTAINER = { id: 1, login: 'chandralegend', type: 'User' };
const ALICE = { id: 101, login: 'alice', type: 'User' };
const BOB = { id: 102, login: 'bob', type: 'User' };
const BOT = { id: 41898282, login: 'github-actions[bot]', type: 'Bot' };

// The agreement last changed at the start of the day the tests' comments are posted.
const AGREEMENT_CHANGED = '2026-10-09T00:00:00Z';

function commitBy(user, sha) {
  return user
    ? { sha, author: { id: user.id, login: user.login }, commit: { author: { name: user.login, email: `${user.login}@example.com` } } }
    : { sha, author: null, commit: { author: { name: 'Mystery Person', email: 'mystery@example.com' } } };
}

class FakeGitHub {
  constructor({ commits, signatures = [], conflicts = 0 }) {
    this.commits = commits;
    this.file = { record: { format: 1, signatures }, sha: 'sha-0', writes: 0 };
    this.conflicts = conflicts;
    this.statuses = [];
    this.comments = [];
    this.commentEdits = 0;
    const self = this;
    this.rest = {
      pulls: {
        listCommits: async () => ({ data: self.commits }),
        get: async ({ pull_number }) => ({ data: self.pull(pull_number) }),
      },
      repos: {
        listCommits: async ({ sha, path: file }) => {
          assert.equal(sha, 'main');
          assert.equal(file, CONFIG.document);
          return { data: [{ commit: { committer: { date: AGREEMENT_CHANGED } } }] };
        },
        getContent: async ({ ref, path: file }) => {
          assert.equal(ref, CONFIG.signaturesBranch);
          assert.equal(file, CONFIG.signaturesPath);
          return {
            data: {
              sha: self.file.sha,
              content: Buffer.from(JSON.stringify(self.file.record)).toString('base64'),
            },
          };
        },
        createOrUpdateFileContents: async ({ sha, content, branch }) => {
          assert.equal(branch, CONFIG.signaturesBranch);
          if (self.conflicts > 0) {
            self.conflicts -= 1;
            self.file.sha = `sha-moved-${self.conflicts}`;
            const error = new Error('conflict');
            error.status = 409;
            throw error;
          }
          assert.equal(sha, self.file.sha, 'must write against the sha it read');
          self.file.record = JSON.parse(Buffer.from(content, 'base64').toString('utf8'));
          self.file.writes += 1;
          self.file.sha = `sha-${self.file.writes}`;
        },
        createCommitStatus: async (status) => {
          self.statuses.push(status);
        },
      },
      issues: {
        listComments: async () => {
          const shown = self.listingLags ? self.comments.slice(0, -1) : self.comments;
          return { data: shown.map((c) => ({ ...c })) };
        },
        createComment: async ({ body }) => {
          self.post(BOT, body);
        },
        updateComment: async ({ comment_id, body }) => {
          self.comments.find((c) => c.id === comment_id).body = body;
          self.commentEdits += 1;
        },
      },
    };
  }

  async paginate(method, params) {
    return (await method(params)).data;
  }

  pull(number = 7, author = this.author) {
    return { number, user: author, head: { sha: 'head-sha' } };
  }

  post(user, body, createdAt = '2026-10-09T12:00:00Z') {
    const comment = {
      id: this.comments.length + 1,
      user,
      body,
      created_at: createdAt,
      html_url: `https://example.com/c/${this.comments.length + 1}`,
    };
    this.comments.push(comment);
    return comment;
  }

  botComments() {
    return this.comments.filter((c) => c.user === BOT);
  }

  lastStatus() {
    return this.statuses[this.statuses.length - 1];
  }
}

const core = { info() {}, setFailed() {} };

function context(eventName, payload) {
  return {
    eventName,
    serverUrl: 'https://github.com',
    repo: { owner: 'leafmonkeylabs', repo: 'salli-core' },
    payload: { repository: { default_branch: 'main' }, ...payload },
  };
}

async function openPull(gh, author) {
  gh.author = author;
  return run({ github: gh, core, root: ROOT, context: context('pull_request_target', { pull_request: gh.pull(7, author) }) });
}

// Posts a comment on the pull request and runs the check the way GitHub would.
async function comment(gh, user, body, { number = 7, createdAt } = {}) {
  const posted = gh.post(user, body, createdAt);
  return run({
    github: gh,
    core,
    root: ROOT,
    context: context('issue_comment', { issue: { number, pull_request: {} }, comment: posted }),
  });
}

test('the sign phrase tolerates case, spacing and a missing full stop, and nothing else', () => {
  assert.ok(isSignature(PHRASE, PHRASE));
  assert.ok(isSignature(`  ${PHRASE.toUpperCase().replace(/ /g, '   ')}  `, PHRASE));
  assert.ok(isSignature(PHRASE.replace(/\.$/, ''), PHRASE));
  assert.ok(!isSignature(`${PHRASE} Also, nice project`, PHRASE));
  assert.ok(!isSignature(`> ${PHRASE}`, PHRASE));
  assert.ok(!isSignature('LGTM', PHRASE));
  assert.ok(isRecheck(' Recheck '));
});

test('the agreement has a version the bot can read', () => {
  assert.match(CONFIG.version, /^\d+(\.\d+)*$/);
  assert.equal(CONFIG.documentSha256.length, 64);
});

test("a maintainer's pull request passes without a comment", async () => {
  const gh = new FakeGitHub({ commits: [commitBy(MAINTAINER, 'a')] });
  await openPull(gh, MAINTAINER);
  assert.equal(gh.lastStatus().state, 'success');
  assert.equal(gh.lastStatus().context, CONFIG.statusContext);
  assert.equal(gh.lastStatus().sha, 'head-sha');
  assert.equal(gh.comments.length, 0);
});

test('bots pass without signing', async () => {
  const bot = { id: 49699333, login: 'dependabot[bot]', type: 'Bot' };
  const gh = new FakeGitHub({ commits: [commitBy(bot, 'a')] });
  await openPull(gh, bot);
  assert.equal(gh.lastStatus().state, 'success');
});

test('an unsigned contributor gets a failing status and one explanatory comment', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a'), commitBy(ALICE, 'b')] });
  await openPull(gh, ALICE);
  await openPull(gh, ALICE); // a new push re-runs the check
  assert.equal(gh.lastStatus().state, 'failure');
  assert.match(gh.lastStatus().description, /@alice/);
  assert.equal(gh.comments.length, 1, 'the comment is kept up to date, not repeated');
  assert.equal(gh.commentEdits, 0, 'an unchanged comment is not rewritten');
  const body = gh.comments[0].body;
  assert.ok(body.includes(MARKER));
  assert.ok(body.includes(PHRASE));
  assert.ok(body.includes('https://github.com/leafmonkeylabs/salli-core/blob/main/CLA.md'));
  assert.ok(body.includes('https://github.com/leafmonkeylabs/salli-core/blob/main/CLA-ENTITY.md'));
});

test('signing by comment records the signature and turns the check green', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  await openPull(gh, ALICE);
  await comment(gh, ALICE, PHRASE);

  assert.deepEqual(gh.file.record.signatures, [
    {
      id: ALICE.id,
      login: 'alice',
      version: CONFIG.version,
      document_sha256: CONFIG.documentSha256,
      signed_at: '2026-10-09T12:00:00Z',
      pull_request: 7,
      comment_url: 'https://example.com/c/2',
    },
  ]);
  assert.equal(gh.lastStatus().state, 'success');
  assert.match(gh.botComments()[0].body, /Everyone in this pull request has signed/);
});

test('signing twice records one signature', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  gh.author = ALICE;
  await comment(gh, ALICE, PHRASE);
  await comment(gh, ALICE, PHRASE);
  assert.equal(gh.file.record.signatures.length, 1);
  assert.equal(gh.file.writes, 1);
});

test('every commit author must sign, not only the pull request author', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a'), commitBy(BOB, 'b')] });
  await openPull(gh, ALICE);
  await comment(gh, ALICE, PHRASE);
  assert.equal(gh.lastStatus().state, 'failure');
  assert.match(gh.lastStatus().description, /@bob/);
  assert.doesNotMatch(gh.lastStatus().description, /@alice/);
  await comment(gh, BOB, PHRASE);
  assert.equal(gh.lastStatus().state, 'success');
});

test("someone not in the pull request can't sign through it", async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  await openPull(gh, ALICE);
  await comment(gh, BOB, PHRASE);
  assert.equal(gh.file.record.signatures.length, 0);
  assert.equal(gh.lastStatus().state, 'failure');
});

test('a signature whose own run was dropped is recorded by the next run', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a'), commitBy(BOB, 'b')] });
  gh.author = ALICE;
  gh.post(ALICE, PHRASE); // its run was cancelled while another one waited
  await comment(gh, BOB, PHRASE);
  assert.deepEqual(gh.file.record.signatures.map((s) => s.login).sort(), ['alice', 'bob']);
  assert.equal(gh.file.writes, 1, 'both are recorded in one write');
  assert.equal(gh.lastStatus().state, 'success');
});

test("a signature still counts when GitHub's comment listing hasn't caught up", async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  gh.author = ALICE;
  gh.listingLags = true;
  await comment(gh, ALICE, PHRASE);
  assert.equal(gh.file.record.signatures.length, 1);
  assert.equal(gh.lastStatus().state, 'success');
});

test('a sign comment from before the agreement last changed does not count', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  gh.author = ALICE;
  await comment(gh, ALICE, PHRASE, { createdAt: '2026-10-08T23:59:59Z' });
  assert.equal(gh.file.record.signatures.length, 0);
  assert.equal(gh.lastStatus().state, 'failure');
});

test('a signature for an older version of the agreement does not count', async () => {
  const old = { id: ALICE.id, login: 'alice', version: '0.9', signed_at: '2025-01-01T00:00:00Z' };
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')], signatures: [old] });
  await openPull(gh, ALICE);
  assert.equal(gh.lastStatus().state, 'failure');
});

test('a signature from an earlier pull request carries over', async () => {
  const earlier = { id: ALICE.id, login: 'alice', version: CONFIG.version, signed_at: '2026-10-01T00:00:00Z' };
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')], signatures: [earlier] });
  await openPull(gh, ALICE);
  assert.equal(gh.lastStatus().state, 'success');
  assert.equal(gh.comments.length, 0);
});

test('a commit whose author has no GitHub account blocks the check', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(MAINTAINER, 'a'), commitBy(null, 'b')] });
  await openPull(gh, MAINTAINER);
  assert.equal(gh.lastStatus().state, 'failure');
  assert.match(gh.botComments()[0].body, /mystery@example\.com/);
  assert.match(gh.lastStatus().description, /unmatched commit authors/);
});

test('other comments re-check without recording anything', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  gh.author = ALICE;
  await comment(gh, ALICE, 'Thanks for the review!');
  await comment(gh, ALICE, 'recheck');
  assert.equal(gh.file.record.signatures.length, 0);
  assert.equal(gh.lastStatus().state, 'failure');
  assert.equal(gh.botComments().length, 1);
});

test("the bot only ever edits its own comment", async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')] });
  gh.author = ALICE;
  const planted = gh.post(ALICE, `${MARKER} please edit me`);
  await comment(gh, ALICE, PHRASE);
  assert.equal(planted.body, `${MARKER} please edit me`);
  assert.equal(gh.lastStatus().state, 'success');
});

test('a concurrent write to the signatures file is retried, not lost', async () => {
  const gh = new FakeGitHub({ commits: [commitBy(ALICE, 'a')], conflicts: 2 });
  gh.author = ALICE;
  await comment(gh, ALICE, PHRASE);
  assert.equal(gh.file.record.signatures.length, 1);
  assert.equal(gh.lastStatus().state, 'success');
});

test('comments on issues (not pull requests) are ignored', async () => {
  const gh = new FakeGitHub({ commits: [] });
  const result = await run({
    github: gh,
    core,
    root: ROOT,
    context: context('issue_comment', {
      issue: { number: 3 },
      comment: { id: 1, user: ALICE, body: PHRASE, created_at: '2026-10-09T12:00:00Z', html_url: 'x' },
    }),
  });
  assert.equal(result, null);
  assert.equal(gh.statuses.length, 0);
});
