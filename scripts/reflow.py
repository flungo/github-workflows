#!/usr/bin/env python3
"""Reflow Markdown prose to semantic line breaks (one sentence per line).

Best-effort migration tool for adopting semantic line breaks in a repo's existing
docs — not repo CI; see docs/runbooks/adopting-markdown-workflows.md. It rewrites
only source whitespace, never rendered output:
every file is gated on render-equivalence (normalised HTML byte-identical before
and after), and any file that would render differently is left untouched.

Scope (first pass; extend later):
  - reflow only TOP-LEVEL prose paragraphs to one sentence per line;
  - PRESERVE hard-break blocks (trailing "  " / "\\" — e.g. **Date:** metadata);
  - LEAVE list/blockquote inner paragraphs hard-wrapped (prefix handling).

Usage:
    pip install markdown-it-py
    python3 reflow.py            # dry-run: sample diffs + per-file gate result
    python3 reflow.py --apply    # write the render-verified reflow in place

Run from the repo root (globs '**/*.md', excluding node_modules).
"""
import sys, re, glob, difflib
from markdown_it import MarkdownIt

APPLY = "--apply" in sys.argv
md = MarkdownIt("commonmark").enable("table")

# Abbreviations after which ". " is NOT a sentence end. Over/under-breaking here
# is style-only — the render gate guarantees correctness either way.
ABBR = re.compile(
    r"(?:^|[\s(\[\"'/])(?:e\.g|i\.e|etc|vs|cf|a\.k\.a|approx|resp|viz|Fig|Dr|Mr|Mrs|Ms|Ph\.D|Inc|Ltd|Jr|Sr)\.$",
    re.I,
)


def split_sentences(text):
    sents, start, i, n = [], 0, 0, len(text)
    in_code = False
    while i < n:
        c = text[i]
        if c == "`":
            in_code = not in_code
            i += 1
            continue
        if not in_code and c in ".?!" and i + 1 < n and text[i + 1] == " ":
            if c == "." and i >= 1 and text[i - 1] == ".":       # ellipsis
                i += 1
                continue
            prefix = text[start:i + 1]
            if c == "." and ABBR.search(prefix):                 # abbreviation
                i += 1
                continue
            sent = prefix.strip()
            if sent:
                sents.append(sent)
            start = i + 2
            i = start
            continue
        i += 1
    tail = text[start:].strip()
    if tail:
        sents.append(tail)
    return sents


def norm_html(s):
    return re.sub(r"\s+", " ", md.render(s)).strip()


def reflow_text(src):
    lines = src.split("\n")
    tokens = md.parse(src)
    spans = [t.map for t in tokens if t.type == "paragraph_open" and t.level == 0 and t.map]
    for a, b in sorted(spans, reverse=True):                     # bottom-up: indices stay valid
        para = lines[a:b]
        if any(re.search(r"(  +|\\)$", x) for x in para):        # preserve hard-break blocks
            continue
        joined = " ".join(x.strip() for x in para).strip()
        new = split_sentences(joined)
        if new and new != [x.rstrip() for x in para]:
            lines[a:b] = new
    return "\n".join(lines)


def main():
    files = sorted(f for f in glob.glob("**/*.md", recursive=True) if "/node_modules/" not in f)
    reflowed, unchanged, failed = [], [], []
    shown = 0
    for f in files:
        orig = open(f, encoding="utf-8").read()
        new = reflow_text(orig)
        if new == orig:
            unchanged.append(f)
            continue
        if norm_html(orig) != norm_html(new):                    # render gate
            failed.append(f)
            continue
        reflowed.append(f)
        if APPLY:
            open(f, "w", encoding="utf-8").write(new)
        elif shown < 2:
            shown += 1
            print(f"\n----- SAMPLE DIFF: {f} -----")
            diff = difflib.unified_diff(orig.splitlines(), new.splitlines(), lineterm="", n=1)
            print("\n".join(list(diff)[:60]))
    print(f"\n=== {'APPLIED' if APPLY else 'DRY-RUN'} ===")
    print(f"reflowed (render-verified): {len(reflowed)}")
    print(f"unchanged: {len(unchanged)}")
    print(f"GATE-FAILED (left untouched): {len(failed)} -> {failed}")


if __name__ == "__main__":
    main()
