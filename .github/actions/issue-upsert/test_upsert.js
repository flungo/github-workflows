// Unit tests for upsert.js, run by test.sh (and so by this action's job in
// action-tests.yml). They drive the action against a fake GitHub client, which
// is the only way to exercise what it does: every path here writes an issue
// into a repository, so the `uses:` smoke step in action-tests.yml can only
// take the one path that writes nothing.
//
// The fake's `paginate` walks pages the way octokit does — until a short page
// comes back — so the >100-open-issues case is a real assertion rather than a
// restatement of the implementation.
'use strict';

const assert = require('node:assert/strict');
const issueUpsert = require('./upsert.js');

const MARKER = '<!-- test-marker -->';
const context = { repo: { owner: 'flungo', repo: 'consumer' } };

function fakeCore() {
  const outputs = {};
  const messages = [];
  const log = (message) => messages.push(message);
  return {
    outputs,
    messages,
    setOutput: (name, value) => { outputs[name] = value; },
    notice: log,
    info: log,
    warning: log,
  };
}

function notFound() {
  const error = new Error('Not Found');
  error.status = 404;
  throw error;
}

function fakeGithub({ issues = [], labels = [] } = {}) {
  const calls = [];
  const store = { issues: issues.map((issue) => ({ ...issue })), labels: new Set(labels) };
  let nextNumber = 9000;

  const listForRepo = async (params) => {
    calls.push(['listForRepo', params]);
    let matching = store.issues.filter((issue) => (issue.state || 'open') === (params.state || 'open'));
    if (params.labels) {
      matching = matching.filter((issue) => (issue.labels || []).includes(params.labels));
    }
    const perPage = params.per_page || 30;
    const page = params.page || 1;
    return { data: matching.slice((page - 1) * perPage, page * perPage) };
  };

  return {
    rest: {
      issues: {
        listForRepo,
        create: async (params) => {
          calls.push(['create', params]);
          return { data: { number: (nextNumber += 1) } };
        },
        update: async (params) => {
          calls.push(['update', params]);
          return { data: {} };
        },
        createComment: async (params) => {
          calls.push(['createComment', params]);
          return { data: {} };
        },
        getLabel: async (params) => {
          calls.push(['getLabel', params]);
          if (!store.labels.has(params.name)) notFound();
          return { data: {} };
        },
        createLabel: async (params) => {
          calls.push(['createLabel', params]);
          store.labels.add(params.name);
          return { data: {} };
        },
      },
    },
    paginate: async (endpoint, params) => {
      const perPage = params.per_page || 30;
      const all = [];
      for (let page = 1; ; page += 1) {
        const { data } = await endpoint({ ...params, per_page: perPage, page });
        all.push(...data);
        if (data.length < perPage) break;
      }
      return all;
    },
    calls,
    names: () => calls.map(([name]) => name),
    paramsFor: (name) => calls.filter(([called]) => called === name).map(([, params]) => params),
  };
}

const tests = [];
const test = (name, fn) => tests.push([name, fn]);

// --- create -----------------------------------------------------------------

test('creates the issue when the condition holds and none is open', async () => {
  const github = fakeGithub();
  const core = fakeCore();
  const result = await issueUpsert({
    github,
    core,
    context,
    env: { MARKER, TITLE: 'Drift detected', BODY: 'Something drifted.', LABEL: 'drift' },
  });

  assert.equal(result.outcome, 'created');
  assert.deepEqual(github.names(), ['listForRepo', 'create']);
  const [created] = github.paramsFor('create');
  assert.equal(created.title, 'Drift detected');
  assert.deepEqual(created.labels, ['drift']);
  assert.equal(core.outputs.outcome, 'created');
  assert.equal(core.outputs['issue-number'], String(result.number));
});

test('prepends the marker to a body that does not carry one', async () => {
  const github = fakeGithub();
  await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Title', BODY: 'Body text.' },
  });

  const [created] = github.paramsFor('create');
  assert.equal(created.body, `${MARKER}\nBody text.`);
  // No label given: nothing to apply, and every open issue is searched.
  assert.deepEqual(created.labels, []);
  assert.equal(github.paramsFor('listForRepo')[0].labels, undefined);
});

test('leaves a body that already carries the marker alone', async () => {
  const github = fakeGithub();
  const body = `${MARKER}\nBuilt by the step that owns the marker.`;
  await issueUpsert({ github, core: fakeCore(), context, env: { MARKER, TITLE: 'Title', BODY: body } });

  const [created] = github.paramsFor('create');
  assert.equal(created.body, body);
  assert.equal(created.body.split(MARKER).length - 1, 1);
});

test('creates a missing label with the colour it was given', async () => {
  const github = fakeGithub();
  await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: {
      MARKER,
      TITLE: 'Title',
      BODY: 'Body.',
      LABEL: 'drift',
      LABEL_COLOR: 'e11d48',
      LABEL_DESCRIPTION: 'Terraform drift was detected and remediated',
    },
  });

  const [label] = github.paramsFor('createLabel');
  assert.equal(label.name, 'drift');
  assert.equal(label.color, 'e11d48');
  assert.equal(label.description, 'Terraform drift was detected and remediated');
});

test('leaves an existing label as it is', async () => {
  const github = fakeGithub({ labels: ['drift'] });
  await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Title', BODY: 'Body.', LABEL: 'drift', LABEL_COLOR: 'e11d48' },
  });

  assert.deepEqual(github.paramsFor('createLabel'), []);
});

test('does not touch the labels API without a colour', async () => {
  const github = fakeGithub();
  await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Title', BODY: 'Body.', LABEL: 'drift' },
  });

  assert.deepEqual(github.names(), ['listForRepo', 'create']);
});

// --- update in place --------------------------------------------------------

test('updates the marked issue in place rather than opening a second one', async () => {
  const github = fakeGithub({
    issues: [
      { number: 5, body: 'An unrelated open issue.', labels: ['drift'] },
      { number: 7, body: `Yesterday's report\n${MARKER}\n`, labels: ['drift'] },
    ],
  });
  const result = await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Still drifting', BODY: 'Today.', LABEL: 'drift' },
  });

  assert.equal(result.outcome, 'updated');
  assert.equal(result.number, 7);
  assert.deepEqual(github.paramsFor('create'), []);
  const [updated] = github.paramsFor('update');
  assert.equal(updated.issue_number, 7);
  assert.equal(updated.title, 'Still drifting');
  assert.equal(updated.body, `${MARKER}\nToday.`);
});

test('searches only open issues, narrowed by the label when one is given', async () => {
  const github = fakeGithub({
    issues: [{ number: 3, body: MARKER, labels: ['drift'], state: 'closed' }],
  });
  const result = await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Title', BODY: 'Body.', LABEL: 'drift' },
  });

  // A closed issue is a resolved one: the condition returning opens a new issue.
  assert.equal(result.outcome, 'created');
  const [listed] = github.paramsFor('listForRepo');
  assert.equal(listed.state, 'open');
  assert.equal(listed.labels, 'drift');
});

test('ignores a pull request carrying the marker', async () => {
  const github = fakeGithub({
    issues: [{ number: 11, body: `A diff quoting ${MARKER}`, pull_request: { url: '…' } }],
  });
  const result = await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Title', BODY: 'Body.' },
  });

  assert.equal(result.outcome, 'created');
  assert.deepEqual(github.paramsFor('update'), []);
});

// --- pagination -------------------------------------------------------------

test('finds the marked issue past the first page of open issues', async () => {
  // 250 open issues, the marked one on the third page: a single unpaginated
  // listing would miss it and open a duplicate on every run.
  const issues = [];
  for (let number = 1; number <= 250; number += 1) {
    issues.push({ number, body: `Open issue ${number}.`, labels: ['markdown-links'] });
  }
  issues[229].body = `${MARKER}\nThe report.`;

  const github = fakeGithub({ issues });
  const result = await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, TITLE: 'Broken links', BODY: 'Still broken.', LABEL: 'markdown-links' },
  });

  assert.equal(result.outcome, 'updated');
  assert.equal(result.number, 230);
  assert.deepEqual(github.paramsFor('create'), []);
  assert.equal(github.paramsFor('listForRepo').length, 3);
});

test('closes a marked issue found past the first page', async () => {
  const issues = [];
  for (let number = 1; number <= 150; number += 1) {
    issues.push({ number, body: `Open issue ${number}.` });
  }
  issues[120].body = `${MARKER}\nThe report.`;

  const github = fakeGithub({ issues });
  const result = await issueUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, STATE: 'absent' },
  });

  assert.equal(result.outcome, 'closed');
  assert.equal(result.number, 121);
});

// --- close when the condition clears ----------------------------------------

test('comments and then closes when the condition clears', async () => {
  const github = fakeGithub({ issues: [{ number: 7, body: MARKER, labels: ['drift'] }] });
  const core = fakeCore();
  const result = await issueUpsert({
    github,
    core,
    context,
    env: { MARKER, STATE: 'absent', LABEL: 'drift', CLOSE_COMMENT: 'No drift — closing.' },
  });

  assert.equal(result.outcome, 'closed');
  assert.deepEqual(github.names(), ['listForRepo', 'createComment', 'update']);
  const [comment] = github.paramsFor('createComment');
  assert.equal(comment.issue_number, 7);
  assert.equal(comment.body, 'No drift — closing.');
  const [closed] = github.paramsFor('update');
  assert.equal(closed.state, 'closed');
  assert.equal(core.outputs['issue-number'], '7');
});

test('closes without a comment when none is given', async () => {
  const github = fakeGithub({ issues: [{ number: 7, body: MARKER }] });
  await issueUpsert({ github, core: fakeCore(), context, env: { MARKER, STATE: 'absent' } });

  assert.deepEqual(github.names(), ['listForRepo', 'update']);
});

test('does nothing when the condition is clear and no issue is open', async () => {
  const github = fakeGithub({ issues: [{ number: 4, body: 'Someone else’s issue.' }] });
  const core = fakeCore();
  const result = await issueUpsert({
    github,
    core,
    context,
    env: { MARKER, STATE: 'absent', CLOSE_COMMENT: 'Never posted.' },
  });

  assert.equal(result.outcome, 'none');
  assert.equal(result.number, undefined);
  assert.equal(core.outputs['issue-number'], '');
  assert.deepEqual(github.names(), ['listForRepo']);
});

// --- fail loud rather than writing nonsense into someone's repository --------

test('rejects a missing marker', async () => {
  await assert.rejects(
    () => issueUpsert({ github: fakeGithub(), core: fakeCore(), context, env: { TITLE: 'T', BODY: 'B' } }),
    /marker is required/,
  );
});

test('rejects an unknown state', async () => {
  await assert.rejects(
    () => issueUpsert({
      github: fakeGithub(),
      core: fakeCore(),
      context,
      env: { MARKER, STATE: 'gone', TITLE: 'T', BODY: 'B' },
    }),
    /state must be/,
  );
});

test('rejects a present state without a title or a body', async () => {
  await assert.rejects(
    () => issueUpsert({ github: fakeGithub(), core: fakeCore(), context, env: { MARKER, BODY: 'B' } }),
    /title is required/,
  );
  await assert.rejects(
    () => issueUpsert({ github: fakeGithub(), core: fakeCore(), context, env: { MARKER, TITLE: 'T' } }),
    /body is required/,
  );
});

(async () => {
  let failures = 0;
  for (const [name, fn] of tests) {
    try {
      await fn();
    } catch (error) {
      failures += 1;
      console.error(`::error::issue-upsert: ${name}: ${error.message}`);
    }
  }
  if (failures > 0) {
    console.error(`issue-upsert: ${failures} of ${tests.length} tests failed`);
    process.exit(1);
  }
  console.log(`issue-upsert: ${tests.length} unit tests passed`);
})();
