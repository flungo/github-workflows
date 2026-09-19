// Keep exactly one open issue in sync with a condition: find the single open
// issue carrying a hidden marker, then create it, update it in place, or
// comment-and-close it once the condition clears.
//
// Three workflows here need that: `flungo-workflows.yml`'s version check,
// `markdown-links.yml`'s external sweep and `terraform-drift.yml`. Pagination,
// marker matching and the close path are each a way to get it subtly wrong, so
// they live here once and are tested once — the argument ADR-009 makes for a
// composite action. `pr-comment-upsert` is the sibling doing this to a pull
// request comment, deliberately a second action rather than a `resource:`
// input on this one — see ADR-018.
//
// Inputs arrive in the environment (action.yml maps them); the `github` client,
// `core` and `context` come from github-script. Exported as a module so
// test_upsert.js can drive every path against a fake client: create, update,
// close and the >100-open-issues pagination case are all API behaviours no
// smoke step could exercise without writing issues into this repository.

function fail(message) {
  throw new Error(`issue-upsert: ${message}`);
}

// The listing is paginated because a repository with more than one page of open
// issues would otherwise stop finding the marker and open a duplicate on every
// run — the exact stacking this action exists to prevent.
//
// `listForRepo` returns pull requests as well as issues: a PR that quotes the
// marker (a diff of the workflow, say) is not the issue being kept in sync.
async function findMarked({ github, owner, repo, marker, label }) {
  const params = { owner, repo, state: 'open', per_page: 100 };
  if (label) params.labels = label;
  const open = await github.paginate(github.rest.issues.listForRepo, params);
  return open.find((issue) => !issue.pull_request && (issue.body || '').includes(marker));
}

// Only when the caller supplied a colour: creating an issue with an unknown
// label creates that label anyway, just in GitHub's default grey and with no
// description. Racing another run to create it is not an error.
async function ensureLabel({ github, owner, repo, name, color, description }) {
  try {
    await github.rest.issues.getLabel({ owner, repo, name });
    return;
  } catch (error) {
    if (error.status && error.status !== 404) throw error;
  }
  try {
    await github.rest.issues.createLabel({ owner, repo, name, color, description });
  } catch (error) {
    if (error.status !== 422) throw error;
  }
}

module.exports = async function issueUpsert({ github, core, context, env = process.env }) {
  const { owner, repo } = context.repo;

  const marker = (env.MARKER || '').trim();
  if (!marker) fail('a marker is required — it is how the next run finds this issue');

  const state = (env.STATE || 'present').trim();
  if (state !== 'present' && state !== 'absent') {
    fail(`state must be 'present' or 'absent', got '${state}'`);
  }

  const label = (env.LABEL || '').trim();
  const existing = await findMarked({ github, owner, repo, marker, label });

  const report = (number, outcome) => {
    core.setOutput('issue-number', number === undefined ? '' : String(number));
    core.setOutput('outcome', outcome);
    return { number, outcome };
  };

  if (state === 'absent') {
    if (!existing) {
      core.info(`Nothing to close: no open issue carries ${marker}.`);
      return report(undefined, 'none');
    }
    const closeComment = env.CLOSE_COMMENT || '';
    if (closeComment.trim()) {
      await github.rest.issues.createComment({
        owner, repo, issue_number: existing.number, body: closeComment,
      });
    }
    await github.rest.issues.update({
      owner, repo, issue_number: existing.number, state: 'closed',
    });
    core.notice(`Closed issue #${existing.number}.`);
    return report(existing.number, 'closed');
  }

  const title = env.TITLE || '';
  const body = env.BODY || '';
  if (!title.trim()) fail("a title is required when state is 'present'");
  if (!body.trim()) fail("a body is required when state is 'present'");

  // The marker has to be *in* the body or the next run cannot find the issue.
  // Prepending it rather than rejecting the body means a caller cannot write an
  // issue that its own next run will duplicate; a body that already carries the
  // marker (because the step building it embedded one) is left alone.
  const markedBody = body.includes(marker) ? body : `${marker}\n${body}`;

  if (existing) {
    await github.rest.issues.update({
      owner, repo, issue_number: existing.number, title, body: markedBody,
    });
    core.notice(`Updated issue #${existing.number}.`);
    return report(existing.number, 'updated');
  }

  const labelColor = (env.LABEL_COLOR || '').trim();
  if (label && labelColor) {
    await ensureLabel({
      github, owner, repo,
      name: label,
      color: labelColor,
      description: env.LABEL_DESCRIPTION || undefined,
    });
  }

  const { data } = await github.rest.issues.create({
    owner, repo, title, body: markedBody, labels: label ? [label] : [],
  });
  core.notice(`Opened issue #${data.number}.`);
  return report(data.number, 'created');
};
