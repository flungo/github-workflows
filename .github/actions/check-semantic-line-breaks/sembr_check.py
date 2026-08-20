#!/usr/bin/env python3
"""Check Markdown prose against the semantic line break MUST rule.

Semantic Line Breaks (<https://sembr.org/>) is mostly a set of SHOULD/MAY
rules — where a break *may* go is a judgement call, and joining lines that were
split legitimately is harder still. This checker deliberately implements only
the one hard rule that can be decided from the source alone:

    A semantic line break MUST occur after a sentence, as punctuated by a
    period (.), exclamation mark (!), or question mark (?).

So it reports exactly one thing: a sentence that ends part-way through a line
with more prose after it — two semantically separable statements sharing a
line. It never reports a line that could have been broken *further*, never
suggests joining anything, and never rewrites a file. (Its ancestor,
`reflow.py` in the markdown-standards plugin, is the one-time migration tool
that does rewrite; this is the repeatable CI gate.)

Only prose is scanned. Frontmatter, fenced and indented code, HTML blocks,
tables, headings (ATX and setext), thematic breaks and link reference
definitions are skipped wholesale, and within a prose line, code spans,
autolinks and link destinations are skipped too. Blockquote and list-item text
*is* prose and is checked, with the structural prefix stripped so a `1.` list
marker is never mistaken for a sentence end.

Where the source is ambiguous the checker stays quiet — a false positive in a
blocking CI check costs far more than a missed break. It therefore ignores a
terminator that follows a known abbreviation ("e.g.", "etc.") or an initialism
("U.S.", "a.m."), and requires the following text to look like the start of a
new sentence (an uppercase letter, a digit, or a code span). The cost is a few
false negatives, listed in the reference docs.

Suppression, for the cases it still gets wrong:

    <!-- sembr-disable-file -->        skip the whole file
    <!-- sembr-disable-next-line -->   skip the next line
    <!-- sembr-disable -->             skip until re-enabled
    <!-- sembr-enable -->

A repo's markdownlint-cli2 `ignores` are read and applied on top of any
`--ignore`, so the two checks skip the same trees without the exclusion being
maintained twice; `--no-markdownlint-config` turns that off.

Usage:
    python3 sembr_check.py [--format text|github] [--ignore GLOB]...
                           [--markdownlint-config PATH | --no-markdownlint-config]
                           [GLOB...]

Exit status: 0 clean, 1 violations found, 2 bad usage.
"""

from __future__ import annotations

import argparse
import glob as globlib
import json
import os
import re
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

# --- structural (block-level) patterns ---------------------------------------

BLOCKQUOTE_RE = re.compile(r"[ \t]{0,3}>[ \t]?")
FENCE_OPEN_RE = re.compile(r"^(`{3,}|~{3,})")
ATX_RE = re.compile(r"^#{1,6}([ \t]|$)")
SETEXT_RE = re.compile(r"^(=+|-+)[ \t]*$")
THEMATIC_RE = re.compile(r"^(?:\*[ \t]*){3,}$|^(?:-[ \t]*){3,}$|^(?:_[ \t]*){3,}$")
LIST_RE = re.compile(r"^([-*+]|\d{1,9}[.)])([ \t]+|$)")
LINKDEF_RE = re.compile(r"^\[[^\]]*\]:")
HTML_RE = re.compile(r"^<(?:!|\?|/?[A-Za-z][A-Za-z0-9-]*(?:[ \t/>]|$))")
DIRECTIVE_RE = re.compile(
    r"<!--[ \t]*sembr-(disable-file|disable-next-line|disable|enable)[ \t]*-->"
)

# Abbreviations after which ". " does not end a sentence. Kept to terms that
# are implausible as the last word of a real sentence — an entry here is a
# permanent blind spot, so "etc" earns its place and "min" does not.
# Initialisms ("U.S.", "a.m.", "i.e.", a lone initial) need no entry: they are
# recognised structurally, as a dotted token whose every segment is one letter.
ABBREVIATIONS = frozenset(
    """
    al approx ca cf dept dr eq etc excl fig ibid inc incl jr ltd mr mrs ms
    ph.d prof resp sr univ viz vol vs
    jan feb mar apr jun jul aug sep sept oct nov dec
    mon tue tues wed thu thur thurs fri sat sun
    """.split()
)

TERMINATORS = ".!?"
# Punctuation that may sit between a terminator and the space after it.
CLOSERS = ")]}\"'’”»*_"
# Markup that may sit between that space and the first letter of the next
# sentence: emphasis, a link, a parenthetical, a quote.
OPENERS = "*_[(<\"'“‘"

WORD_BEFORE_RE = re.compile(r"([A-Za-z][A-Za-z.]*)$")


@dataclass(frozen=True)
class Finding:
    """One sentence that ends part-way through a line."""

    path: str
    line: int  # 1-based
    col: int  # 1-based, at the terminator
    before: str  # tail of the sentence that ended
    after: str  # head of the text that follows it

    @property
    def message(self) -> str:
        return (
            f'sentence ends mid-line: break the line after "{self.before}" '
            f'(before "{self.after}") — a semantic line break MUST occur '
            f"after a sentence"
        )


@dataclass
class ProseLine:
    """A source line's prose content, with the structural prefix removed."""

    line: int  # 1-based
    offset: int  # characters stripped from the front of the source line
    text: str


# --- block scanning -----------------------------------------------------------


def _strip_blockquotes(line: str) -> tuple[int, str]:
    """Drop any leading `>` markers; return (characters dropped, remainder)."""
    offset = 0
    while True:
        match = BLOCKQUOTE_RE.match(line, offset)
        if not match:
            return offset, line[offset:]
        offset = match.end()


def _plain(line: str) -> str:
    """The line's content with blockquote markers and indentation removed."""
    return _strip_blockquotes(line)[1].strip()


def _is_table_delimiter(content: str) -> bool:
    """True for a GFM table's `| --- | --- |` row (a pipe is required, so a
    bare `---` stays a thematic break or a setext underline)."""
    return "|" in content and "-" in content and re.fullmatch(r"[ \t|:-]+", content) is not None


def _disabled_lines(lines: list[str]) -> tuple[bool, set[int]]:
    """Resolve the `<!-- sembr-* -->` directives to (skip file, skipped lines)."""
    disabled: set[int] = set()
    off = False
    for index, line in enumerate(lines):
        for directive in DIRECTIVE_RE.findall(line):
            if directive == "disable-file":
                return True, set()
            if directive == "disable":
                off = True
            elif directive == "enable":
                off = False
            elif directive == "disable-next-line":
                disabled.add(index + 2)  # 1-based, the *next* line
        if off:
            disabled.add(index + 1)
    return False, disabled


def prose_lines(src: str) -> list[ProseLine]:
    """Every line of `src` that is prose, with its structural prefix stripped.

    A single forward pass with just enough CommonMark block structure to know
    what is *not* prose. Anything it cannot classify confidently is treated as
    prose only when it plainly is — the scan errs towards skipping.
    """
    lines = src.split("\n")
    out: list[ProseLine] = []

    start = 0
    # YAML/TOML frontmatter, but only when it is closed — an unclosed `---` on
    # line 1 is a thematic break, not a truncated frontmatter block.
    if lines and lines[0].rstrip() in ("---", "+++"):
        delimiter = lines[0].rstrip()
        for index in range(1, len(lines)):
            if lines[index].rstrip() == delimiter:
                start = index + 1
                break

    fence: tuple[str, int] | None = None  # (fence char, length)
    in_comment = False
    in_html_block = False
    in_indented_code = False
    in_table = False
    list_stack: list[int] = []  # content column of each open list item
    para_start: int | None = None  # index into `out` of the current paragraph

    def close_paragraph() -> None:
        nonlocal para_start
        para_start = None

    for index in range(start, len(lines)):
        raw = lines[index]
        quote_offset, rest = _strip_blockquotes(raw)
        indent = len(rest) - len(rest.lstrip(" \t"))
        content = rest[indent:]
        offset = quote_offset + indent

        if content == "":
            close_paragraph()
            in_table = False
            in_html_block = False  # an HTML block runs to the next blank line
            continue

        if in_html_block:
            continue

        if fence is not None:
            char, length = fence
            if content[0] == char and re.fullmatch(re.escape(char) + "{%d,}[ \t]*" % length, content):
                fence = None
            continue

        if in_comment:
            if "-->" in raw:
                in_comment = False
            continue

        # An open list item keeps its content column; a line indented less than
        # that has left the item.
        while list_stack and indent < list_stack[-1]:
            list_stack.pop()
        base = list_stack[-1] if list_stack else 0

        if in_indented_code:
            if indent >= base + 4:
                continue
            in_indented_code = False

        # An indented code block cannot interrupt a paragraph, so it only
        # starts where no paragraph is open.
        if para_start is None and indent >= base + 4:
            in_indented_code = True
            continue

        if FENCE_OPEN_RE.match(content):
            fence = (content[0], len(FENCE_OPEN_RE.match(content).group(1)))
            close_paragraph()
            continue

        if HTML_RE.match(content):
            # A comment ends on the line carrying `-->`, so prose may resume
            # immediately after it — which is what makes the one-line
            # `<!-- sembr-disable-next-line -->` directive usable. Any other
            # HTML block runs to the next blank line.
            if content.startswith("<!--"):
                in_comment = "-->" not in content
            else:
                in_html_block = True
            close_paragraph()
            continue

        # A setext underline turns the paragraph above it into a heading, so
        # retract the lines already collected for that paragraph.
        if para_start is not None and SETEXT_RE.match(content):
            del out[para_start:]
            close_paragraph()
            continue

        if ATX_RE.match(content) or THEMATIC_RE.match(content) or LINKDEF_RE.match(content):
            close_paragraph()
            continue

        if _is_table_delimiter(content) or (
            "|" in content and _is_table_delimiter(_plain(lines[index + 1]) if index + 1 < len(lines) else "")
        ):
            in_table = True
            close_paragraph()
            continue
        if in_table and "|" in content:
            close_paragraph()
            continue
        in_table = False

        marker = LIST_RE.match(content)
        if marker:
            offset += len(marker.group(0))
            content = content[len(marker.group(0)) :]
            list_stack.append(indent + len(marker.group(0)))
            close_paragraph()
            if content == "":
                continue

        if para_start is None:
            para_start = len(out)
        out.append(ProseLine(line=index + 1, offset=offset, text=content))

    return out


# --- inline scanning ----------------------------------------------------------


def _is_abbreviation(text: str, i: int) -> bool:
    """True if the `.` at `text[i]` belongs to an abbreviation or initialism."""
    match = WORD_BEFORE_RE.search(text[:i])
    if not match:
        return False
    token = match.group(1).lower()
    if token in ABBREVIATIONS:
        return True
    # An initialism — every dot-separated segment a single letter: "U.S.",
    # "a.m.", "i.e.", or a lone initial such as "J.".
    return all(len(segment) == 1 for segment in token.split(".") if segment)


def _starts_a_sentence(text: str, i: int) -> bool:
    """True if `text[i:]` reads as the start of a new sentence.

    Requiring this is what keeps the check quiet on an abbreviation nobody
    thought to list: those are almost always followed by lowercase.
    """
    if text[i] == "`":  # a code span routinely opens a sentence in these docs
        return True
    while i < len(text) and text[i] in OPENERS:
        i += 1
    return i < len(text) and (text[i].isupper() or text[i].isdigit())


def line_violations(text: str) -> list[tuple[int, str, str]]:
    """Sentence ends followed by more prose, as (index, before, after)."""
    found: list[tuple[int, str, str]] = []
    fence = 0  # length of the backtick run that opened the current code span
    i = 0
    n = len(text)
    while i < n:
        char = text[i]

        if char == "`":
            run = len(text[i:]) - len(text[i:].lstrip("`"))
            if fence == 0:
                fence = run
            elif run == fence:
                fence = 0
            i += run
            continue

        # Inside a code span nothing is markup — not even a backslash escape.
        if fence:
            i += 1
            continue

        if char == "\\":
            i += 2
            continue

        if char == "<":  # autolink: <https://…> or <name@example.com>
            match = re.match(r"<[^ \t<>]*>", text[i:])
            if match:
                i += match.end()
                continue

        if char == "]" and text[i + 1 : i + 2] == "(":  # inline link destination
            depth, j = 1, i + 2
            while j < n and depth:
                if text[j] == "\\":
                    j += 2
                    continue
                depth += (text[j] == "(") - (text[j] == ")")
                j += 1
            i = j
            continue

        if char not in TERMINATORS:
            i += 1
            continue

        # Ellipsis: not a sentence end we can be sure of.
        if char == "." and (text[i - 1 : i] == "." or text[i + 1 : i + 2] == "."):
            i += 1
            continue

        j = i + 1
        while j < n and text[j] in CLOSERS:
            j += 1
        if j >= n or text[j] not in " \t":
            i += 1
            continue

        k = j
        while k < n and text[k] in " \t":
            k += 1
        if k >= n:  # only trailing whitespace follows — the break is there
            break

        if char == "." and _is_abbreviation(text, i):
            i += 1
            continue
        if not _starts_a_sentence(text, k):
            i += 1
            continue

        found.append((i, text[max(0, i - 32) : j].strip(), text[k : k + 32].strip()))
        i = k

    return found


# --- file / driver ------------------------------------------------------------


def check_text(src: str, path: str = "<text>") -> list[Finding]:
    """Every semantic-line-break violation in one document."""
    lines = src.split("\n")
    skip_file, disabled = _disabled_lines(lines)
    if skip_file:
        return []
    findings: list[Finding] = []
    for prose in prose_lines(src):
        if prose.line in disabled:
            continue
        for index, before, after in line_violations(prose.text):
            findings.append(
                Finding(
                    path=path,
                    line=prose.line,
                    col=prose.offset + index + 1,
                    before=before,
                    after=after,
                )
            )
    return findings


def check_file(path: str) -> list[Finding]:
    with open(path, encoding="utf-8") as handle:
        return check_text(handle.read(), path)


ALWAYS_IGNORED = (".git", "node_modules")

# markdownlint-cli2 config files that can carry `ignores`, in its own
# precedence order. The `.markdownlint.*` family carries only the `config`
# object, so there is nothing here to read from those.
MARKDOWNLINT_CONFIGS = (
    ".markdownlint-cli2.jsonc",
    ".markdownlint-cli2.yaml",
    ".markdownlint-cli2.cjs",
    ".markdownlint-cli2.mjs",
)


def _strip_jsonc(text: str) -> str:
    """Remove comments and trailing commas so `json` can parse a JSONC file.

    Scanned rather than regexed because a `//` inside a string literal is data,
    not a comment — the rule paths in a real config are full of them.
    """
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch == '"':                                    # copy a string whole
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\":
                    i += 1
                    if i < n:
                        out.append(text[i])
                elif text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if text.startswith("//", i):
            i = text.find("\n", i)
            if i == -1:
                break
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            i = n if end == -1 else end + 2
            continue
        out.append(ch)
        i += 1
    # Trailing commas are legal in JSONC and fatal to json.loads.
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def markdownlint_pattern(pattern: str) -> str:
    """Translate one markdownlint-cli2 `ignores` glob into this checker's dialect.

    globby reads `**/` as "zero or more directories", so `**/fixtures/**` covers
    a top-level `fixtures/` as well as a nested one. This checker spells "at any
    depth" as a bare name instead (see `_matches`), and its `**/…` needs at
    least one leading directory — so importing such a pattern verbatim would
    quietly leave the top-level copy in scope, which is the asymmetry that
    reading the config exists to remove. Stripping the wildcard prefix and the
    "everything beneath" suffix makes the two agree.

    A `*` inside a path segment is left alone. globby confines it to one
    segment where `_matches` lets it span separators, so such a pattern can
    exclude more here than it does there — the direction that costs coverage of
    the prose gate, so those are reported rather than applied silently.
    """
    result = pattern.strip()
    while result.startswith("**/"):
        result = result[3:]
    while result.endswith("/**"):
        result = result[:-3]
    return result.rstrip("/")


def load_markdownlint_ignores(
    path: str | None = None, root: str = "."
) -> tuple[list[str], str | None, list[str]]:
    """Read `ignores` from a markdownlint-cli2 config: (patterns, source, notes).

    `notes` carries anything the caller should be told rather than left to
    discover from a surprising scan: a config this cannot read, or a pattern
    whose meaning may not survive the translation. Missing config is not a
    note — most repos have none, and saying so every run is noise.
    """
    notes: list[str] = []
    if path is None:
        for candidate in MARKDOWNLINT_CONFIGS:
            candidate_path = os.path.join(root, candidate)
            if os.path.isfile(candidate_path):
                path = candidate_path
                break
        else:
            return [], None, notes
    elif not os.path.isfile(path):
        return [], None, [f"markdownlint config not found: {path}"]

    name = os.path.basename(path)
    if name.endswith((".cjs", ".mjs")):
        return [], path, [
            f"{path} is JavaScript and cannot be read here — "
            "pass any shared exclusions via --ignore"
        ]

    try:
        text = Path(path).read_text(encoding="utf-8")
        if name.endswith(".yaml") or name.endswith(".yml"):
            try:
                import yaml  # noqa: PLC0415 — optional, and only on this path
            except ImportError:
                return [], path, [
                    f"{path} needs PyYAML to read — install it, switch to "
                    ".markdownlint-cli2.jsonc, or pass --ignore"
                ]
            data = yaml.safe_load(text) or {}
        else:
            data = json.loads(_strip_jsonc(text))
    except Exception as error:                           # malformed, unreadable
        return [], path, [f"{path} could not be read ({error}) — ignoring it"]

    raw = data.get("ignores") if isinstance(data, dict) else None
    if not isinstance(raw, list):
        return [], path, notes

    patterns = []
    for entry in raw:
        if not isinstance(entry, str) or not entry.strip():
            continue
        if entry.lstrip().startswith("!"):               # a re-inclusion
            notes.append(f"{path}: ignoring negated pattern {entry!r}")
            continue
        translated = markdownlint_pattern(entry)
        if translated:
            if "*" in translated.replace("**", ""):
                notes.append(
                    f"{path}: {entry!r} has a wildcard inside a path segment, "
                    "which may exclude more here than in markdownlint"
                )
            patterns.append(translated)
    return patterns, path, notes


def _matches(path: str, pattern: str) -> bool:
    """fnmatch, with gitignore's anchoring rule and directory shorthand.

    A pattern naming a directory covers everything beneath it. Anchoring
    follows gitignore: a pattern **containing a slash** is relative to the
    scan root, while a bare name matches at any depth — so `node_modules`
    catches every one, and `docs/generated` catches only the top-level one
    rather than any directory that happens to end that way.

    The distinction is load-bearing, not cosmetic: `markdown-sembr.yml` drops
    this repo's own checkout into the caller's workspace, so a caller ignoring
    `docs/x` must not thereby also ignore `.github-workflows/docs/x` and mask
    whether that checkout is being excluded at all.
    """
    pattern = pattern.rstrip("/")
    candidates = [pattern, pattern + "/*", pattern + "/**"]
    if "/" not in pattern:
        candidates += ["**/" + pattern, "**/" + pattern + "/*"]
    return any(fnmatch(path, candidate) for candidate in candidates)


def collect_files(patterns: list[str], ignores: list[str]) -> list[str]:
    """Expand the globs, relative to the working directory, minus the ignores.

    `pathlib` rather than `glob` so that `**/*.md` reaches documentation under
    a dot directory — `.github/` most of all. Every hidden directory is then in
    scope, which is why `.git` is ignored unconditionally.
    """
    paths: set[str] = set()
    for pattern in patterns:
        matches = (
            globlib.glob(pattern, recursive=True)
            if os.path.isabs(pattern)
            else Path(".").glob(pattern)
        )
        for match in matches:
            if os.path.isfile(match):
                paths.add(os.path.relpath(match).replace(os.sep, "/"))
    ignores = list(ignores) + list(ALWAYS_IGNORED)
    return sorted(p for p in paths if not any(_matches(p, i) for i in ignores))


def _annotation(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A").replace(",", "%2C")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sembr_check.py",
        description="Check that Markdown prose breaks lines after every sentence.",
    )
    parser.add_argument(
        "globs",
        nargs="*",
        help="glob patterns to check (default: **/*.md)",
    )
    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="GLOB",
        help="glob of paths to skip; repeatable",
    )
    parser.add_argument(
        "--format",
        choices=("text", "github"),
        default="text",
        help="text (default) or github workflow-command annotations",
    )
    parser.add_argument(
        "--markdownlint-config",
        metavar="PATH",
        help="markdownlint-cli2 config to inherit `ignores` from "
        "(default: whichever one is in the scan root)",
    )
    parser.add_argument(
        "--no-markdownlint-config",
        dest="markdownlint_config",
        action="store_const",
        const=False,
        help="do not inherit `ignores` from a markdownlint-cli2 config",
    )
    args = parser.parse_args(argv)

    ignores = list(args.ignore)
    if args.markdownlint_config is not False:
        inherited, source, notes = load_markdownlint_ignores(args.markdownlint_config)
        for note in notes:
            print(f"sembr: {note}", file=sys.stderr)
        if inherited:
            print(
                f"sembr: inheriting {len(inherited)} ignore(s) from {source}",
                file=sys.stderr,
            )
            ignores += inherited

    files = collect_files(args.globs or ["**/*.md"], ignores)
    findings = [finding for path in files for finding in check_file(path)]

    for finding in findings:
        if args.format == "github":
            print(
                f"::error file={_annotation(finding.path)},line={finding.line},"
                f"col={finding.col}::{_annotation(finding.message)}"
            )
        else:
            print(f"{finding.path}:{finding.line}:{finding.col}: {finding.message}")

    if findings:
        affected = len({finding.path for finding in findings})
        print(
            f"\nsembr: {len(findings)} sentence(s) not on their own line "
            f"across {affected} of {len(files)} file(s).",
            file=sys.stderr,
        )
        return 1

    print(f"sembr: {len(files)} file(s) checked, no violations.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
