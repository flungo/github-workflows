// Unit tests for upsert.js, run by test.sh (and so by this action's job in
// action-tests.yml). They drive the action against a fake GitHub client,
// because every path that does anything posts, edits or deletes a comment on a
// real pull request — the `uses:` smoke step in action-tests.yml can only take
// the one path that writes nothing.
//
// The fake's `paginate` walks pages the way octokit does — until a short page
// comes back — so the long-pull-request case is a real assertion rather than a
// restatement of the implementation.
'use strict';

const assert = require('node:assert/strict');
const prCommentUpsert = require('./upsert.js');

const MARKER = '<!-- terraform-plan -->';
const context = { repo: { owner: 'flungo', repo: 'consumer' }, issue: { number: 42 } };

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

function fakeGithub({ comments = [] } = {}) {
  const calls = [];
  const store = comments.map((comment) => ({ ...comment }));
  let nextId = 7000;

  const listComments = async (params) => {
    calls.push(['listComments', params]);
    const mine = store.filter((comment) => comment.issue_number === undefined
      || comment.issue_number === params.issue_number);
    const perPage = params.per_page || 30;
    const page = params.page || 1;
    return { data: mine.slice((page - 1) * perPage, page * perPage) };
  };

  return {
    rest: {
      issues: {
        listComments,
        createComment: async (params) => {
          calls.push(['createComment', params]);
          return { data: { id: (nextId += 1) } };
        },
        updateComment: async (params) => {
          calls.push(['updateComment', params]);
          return { data: {} };
        },
        deleteComment: async (params) => {
          calls.push(['deleteComment', params]);
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

test('posts the comment when the pull request has none carrying the marker', async () => {
  const github = fakeGithub({ comments: [{ id: 1, body: 'A review remark.' }] });
  const core = fakeCore();
  const result = await prCommentUpsert({
    github,
    core,
    context,
    env: { MARKER, BODY: 'Plan: 1 to add.' },
  });

  assert.equal(result.outcome, 'created');
  assert.deepEqual(github.names(), ['listComments', 'createComment']);
  const [created] = github.paramsFor('createComment');
  assert.equal(created.issue_number, 42);
  assert.equal(created.body, `${MARKER}\nPlan: 1 to add.`);
  assert.equal(core.outputs.outcome, 'created');
  assert.equal(core.outputs['comment-id'], String(result.id));
});

test('leaves a body that already carries the marker alone', async () => {
  const github = fakeGithub();
  const body = `${MARKER}\nBuilt by the step that owns the marker.`;
  await prCommentUpsert({ github, core: fakeCore(), context, env: { MARKER, BODY: body } });

  const [created] = github.paramsFor('createComment');
  assert.equal(created.body, body);
  assert.equal(created.body.split(MARKER).length - 1, 1);
});

// --- update in place --------------------------------------------------------

test('updates the marked comment rather than posting another', async () => {
  const github = fakeGithub({
    comments: [
      { id: 1, body: 'A review remark.' },
      { id: 2, body: `${MARKER}\nThe previous push's plan.` },
    ],
  });
  const result = await prCommentUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, BODY: 'This push’s plan.' },
  });

  assert.equal(result.outcome, 'updated');
  assert.equal(result.id, 2);
  assert.deepEqual(github.paramsFor('createComment'), []);
  const [updated] = github.paramsFor('updateComment');
  assert.equal(updated.comment_id, 2);
  assert.equal(updated.body, `${MARKER}\nThis push’s plan.`);
});

test('comments on the pull request it is told to, over the triggering one', async () => {
  const github = fakeGithub({
    comments: [{ id: 5, issue_number: 99, body: `${MARKER}\nOld.` }],
  });
  const result = await prCommentUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, BODY: 'New.', ISSUE_NUMBER: '99' },
  });

  assert.equal(result.outcome, 'updated');
  assert.equal(github.paramsFor('listComments')[0].issue_number, 99);
});

// --- pagination -------------------------------------------------------------

test('finds the marked comment past the first page', async () => {
  // 250 comments, the marked one on the third page: the API's default page of
  // 30 — and even a single page of 100 — would miss it and post a duplicate on
  // every push.
  const comments = [];
  for (let id = 1; id <= 250; id += 1) comments.push({ id, body: `Comment ${id}.` });
  comments[229].body = `${MARKER}\nThe plan.`;

  const github = fakeGithub({ comments });
  const result = await prCommentUpsert({
    github,
    core: fakeCore(),
    context,
    env: { MARKER, BODY: 'The new plan.' },
  });

  assert.equal(result.outcome, 'updated');
  assert.equal(result.id, 230);
  assert.deepEqual(github.paramsFor('createComment'), []);
  assert.equal(github.paramsFor('listComments').length, 3);
  // 100 per page, not the API's default of 30.
  assert.equal(github.paramsFor('listComments')[0].per_page, 100);
});

// --- remove when the condition clears ---------------------------------------

test('deletes the marked comment when the condition clears', async () => {
  const github = fakeGithub({ comments: [{ id: 3, body: `${MARKER}\nStale.` }] });
  const core = fakeCore();
  const result = await prCommentUpsert({
    github,
    core,
    context,
    env: { MARKER, STATE: 'absent' },
  });

  assert.equal(result.outcome, 'deleted');
  assert.deepEqual(github.names(), ['listComments', 'deleteComment']);
  assert.equal(github.paramsFor('deleteComment')[0].comment_id, 3);
  assert.equal(core.outputs['comment-id'], '3');
});

test('does nothing when the condition is clear and no comment is there', async () => {
  const github = fakeGithub({ comments: [{ id: 1, body: 'A review remark.' }] });
  const core = fakeCore();
  const result = await prCommentUpsert({
    github,
    core,
    context,
    env: { MARKER, STATE: 'absent' },
  });

  assert.equal(result.outcome, 'none');
  assert.equal(result.id, undefined);
  assert.equal(core.outputs['comment-id'], '');
  assert.deepEqual(github.names(), ['listComments']);
});

// --- fail loud rather than commenting nonsense onto someone's pull request ---

test('rejects a missing marker', async () => {
  await assert.rejects(
    () => prCommentUpsert({ github: fakeGithub(), core: fakeCore(), context, env: { BODY: 'B' } }),
    /marker is required/,
  );
});

test('rejects an unknown state', async () => {
  await assert.rejects(
    () => prCommentUpsert({
      github: fakeGithub(),
      core: fakeCore(),
      context,
      env: { MARKER, STATE: 'closed', BODY: 'B' },
    }),
    /state must be/,
  );
});

test('rejects a present state without a body', async () => {
  await assert.rejects(
    () => prCommentUpsert({ github: fakeGithub(), core: fakeCore(), context, env: { MARKER } }),
    /body is required/,
  );
});

test('rejects a run with no pull request to comment on', async () => {
  await assert.rejects(
    () => prCommentUpsert({
      github: fakeGithub(),
      core: fakeCore(),
      context: { repo: context.repo },
      env: { MARKER, BODY: 'B' },
    }),
    /no pull request to comment on/,
  );
});

test('rejects a nonsense issue-number rather than guessing', async () => {
  await assert.rejects(
    () => prCommentUpsert({
      github: fakeGithub(),
      core: fakeCore(),
      context,
      env: { MARKER, BODY: 'B', ISSUE_NUMBER: 'twelve' },
    }),
    /issue-number must be/,
  );
});

(async () => {
  let failures = 0;
  for (const [name, fn] of tests) {
    try {
      await fn();
    } catch (error) {
      failures += 1;
      console.error(`::error::pr-comment-upsert: ${name}: ${error.message}`);
    }
  }
  if (failures > 0) {
    console.error(`pr-comment-upsert: ${failures} of ${tests.length} tests failed`);
    process.exit(1);
  }
  console.log(`pr-comment-upsert: ${tests.length} unit tests passed`);
})();
