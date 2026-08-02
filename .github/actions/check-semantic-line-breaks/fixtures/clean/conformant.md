---
title: A fixture whose frontmatter holds two sentences. Deliberately so.
---

# A conformant fixture

Every prose sentence here sits on its own line.
The file is the green half of the action's wiring smoke test in
`action-tests.yml`, and the target of this repo's own `markdown-sembr` job,
so a regression that starts flagging valid prose fails CI rather than sitting
unnoticed in a consumer.

It also carries one of each construct the checker must look straight past.
A false positive in a blocking check is worse than a missed break,
so the quiet cases are the ones worth pinning down.

## Constructs the check must skip

Prose may end a sentence at the end of a line, e.g. this one.
Abbreviations such as etc. and initialisms such as the U.S. Government
do not end a sentence,
and neither does a version like v1.2 or a decimal like 3.14.

- A list item, broken after its sentence.
  Its continuation line is prose too.
- A second item.
  1. A nested ordered item, whose `1.` marker is not a sentence end.
  2. Another one.

> A blockquote is prose as well.
> It is checked with the `>` markers stripped.

| Column | Purpose |
| --- | --- |
| Table cells | Are skipped. Even with two sentences. |

```sh
# Fenced code is skipped. Even this comment. And this one.
echo one. echo two.
```

    Indented code is skipped too. Same as above.

<div>
An HTML block runs to the next blank line. It is skipped.
</div>

<!-- sembr-disable-next-line -->
A line the directive exempts. So this second sentence is allowed.
