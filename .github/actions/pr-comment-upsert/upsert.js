// Keep exactly one pull request comment in sync with a condition: find the
// single comment carrying a hidden marker, then create it, update it in place,
// or delete it once the condition clears.
//
// The sibling of `issue-upsert`, deliberately a separate action rather than a
// `resource:` input on one (ADR-018): the two share a marker search and nothing
// else — a comment has no title, no labels, no open/closed state, and is
// addressed by its own id on a resource that is superseded by its next
// revision. What they do share is the care a marker search needs: a listing
// read one page at a time stops finding the marker and posts a duplicate, and
// for comments the API serves 30 per page unless asked otherwise.
//
// Inputs arrive in the environment (action.yml maps them); the `github` client,
// `core` and `context` come from github-script. Exported as a module so
// test_upsert.js can drive every path against a fake client — each of them
// writes a comment onto a real pull request otherwise.

function fail(message) {
  throw new Error(`pr-comment-upsert: ${message}`);
}

// Paginated: on a long pull request the API's default page of 30 comments
// stops carrying the marked one, and every later run posts another copy.
async function findMarked({ github, owner, repo, issueNumber, marker }) {
  const comments = await github.paginate(github.rest.issues.listComments, {
    owner, repo, issue_number: issueNumber, per_page: 100,
  });
  return comments.find((comment) => (comment.body || '').includes(marker));
}

module.exports = async function prCommentUpsert({ github, core, context, env = process.env }) {
  const { owner, repo } = context.repo;

  const marker = (env.MARKER || '').trim();
  if (!marker) fail('a marker is required — it is how the next run finds this comment');

  const state = (env.STATE || 'present').trim();
  if (state !== 'present' && state !== 'absent') {
    fail(`state must be 'present' or 'absent', got '${state}'`);
  }

  // The pull request being commented on: the one that triggered the run unless
  // the caller names another. A workflow that is not running on a pull request
  // has to say which one, rather than have the action guess.
  const requested = (env.ISSUE_NUMBER || '').trim();
  const issueNumber = requested ? Number(requested) : (context.issue || {}).number;
  if (!Number.isInteger(issueNumber) || issueNumber <= 0) {
    fail(requested
      ? `issue-number must be a positive whole number, got '${requested}'`
      : 'no pull request to comment on — run this on a pull request or pass issue-number');
  }

  const existing = await findMarked({ github, owner, repo, issueNumber, marker });

  const report = (id, outcome) => {
    core.setOutput('comment-id', id === undefined ? '' : String(id));
    core.setOutput('outcome', outcome);
    return { id, outcome };
  };

  if (state === 'absent') {
    if (!existing) {
      core.info(`Nothing to remove: no comment on #${issueNumber} carries ${marker}.`);
      return report(undefined, 'none');
    }
    // Deleted rather than edited into a "never mind": a comment says what is
    // true of the current head, and there is no state to leave behind the way
    // closing an issue does.
    await github.rest.issues.deleteComment({ owner, repo, comment_id: existing.id });
    core.notice(`Removed the marked comment on #${issueNumber}.`);
    return report(existing.id, 'deleted');
  }

  const body = env.BODY || '';
  if (!body.trim()) fail("a body is required when state is 'present'");

  // The marker has to be *in* the comment or the next run cannot find it.
  // Prepending it rather than rejecting the body means a caller cannot post a
  // comment that its own next run would duplicate; a body that already carries
  // the marker (because the step building it embedded one) is left alone.
  const markedBody = body.includes(marker) ? body : `${marker}\n${body}`;

  if (existing) {
    await github.rest.issues.updateComment({ owner, repo, comment_id: existing.id, body: markedBody });
    core.notice(`Updated the plan comment on #${issueNumber}.`);
    return report(existing.id, 'updated');
  }

  const { data } = await github.rest.issues.createComment({
    owner, repo, issue_number: issueNumber, body: markedBody,
  });
  core.notice(`Posted a comment on #${issueNumber}.`);
  return report(data.id, 'created');
};
