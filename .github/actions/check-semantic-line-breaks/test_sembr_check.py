#!/usr/bin/env python3
"""Unit tests for sembr_check.py, run by this action's test.sh (and locally
with `python3 -m unittest discover`).

Two things carry the weight here. `MustBreakTest` proves the rule is actually
enforced; `NoFalsePositiveTest` proves it stays quiet everywhere it should,
which for a blocking CI check is the more valuable half — every case there is a
construct that a naive "split on `. `" would have flagged.
"""

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sembr_check  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sembr_check.py")


def violations(src):
    """(line, col) of every finding in a dedented document."""
    return [(f.line, f.col) for f in sembr_check.check_text(textwrap.dedent(src).lstrip("\n"))]


class MustBreakTest(unittest.TestCase):
    """Sentence ends that MUST have been a line break."""

    def test_two_sentences_on_one_line(self):
        self.assertEqual(violations("The first one. The second one.\n"), [(1, 14)])

    def test_exclamation_and_question_marks(self):
        self.assertEqual(violations("Stop there! Then continue.\n"), [(1, 11)])
        self.assertEqual(violations("Why not? Because it breaks.\n"), [(1, 8)])

    def test_three_sentences_report_each_break(self):
        self.assertEqual(violations("One here. Two here. Three here.\n"), [(1, 9), (1, 19)])

    def test_reports_the_second_line_of_a_paragraph(self):
        self.assertEqual(violations("A clean first line.\nA second line. With a tail.\n"), [(2, 14)])

    def test_list_item_prose_is_checked_past_the_marker(self):
        # Column 7 is the `.` of "item.", not the `.` of the "1." marker.
        self.assertEqual(violations("1. An item. And more.\n"), [(1, 11)])
        self.assertEqual(violations("- An item. And more.\n"), [(1, 10)])

    def test_nested_list_continuation_is_checked(self):
        self.assertEqual(
            violations(
                """
                - Outer item.
                  - Inner item. With a tail.
                """
            ),
            [(2, 15)],
        )

    def test_blockquote_prose_is_checked(self):
        self.assertEqual(violations("> Quoted text. And more.\n"), [(1, 14)])
        self.assertEqual(violations("> > Nested quote. And more.\n"), [(1, 17)])

    def test_sentence_ending_in_a_closing_bracket_or_quote(self):
        self.assertEqual(violations('He said "no thanks." Then he left.\n'), [(1, 19)])
        self.assertEqual(violations("(An aside.) Then the point.\n"), [(1, 10)])

    def test_sentence_ending_inside_emphasis(self):
        self.assertEqual(violations("*Emphasised.* Then plain text.\n"), [(1, 12)])

    def test_next_sentence_may_start_with_markup_or_a_digit(self):
        self.assertEqual(violations("First one. [A link](https://example.com) follows.\n"), [(1, 10)])
        self.assertEqual(violations("First one. 42 follows.\n"), [(1, 10)])
        self.assertEqual(violations("First one. `code` follows.\n"), [(1, 10)])

    def test_sentence_after_an_abbreviation_earlier_in_the_line(self):
        self.assertEqual(violations("Use e.g. this one. Then that one.\n"), [(1, 18)])

    def test_sentence_after_a_url(self):
        self.assertEqual(violations("See https://example.com/docs. Then read it.\n"), [(1, 29)])

    def test_column_accounts_for_indentation_and_quote_markers(self):
        self.assertEqual(violations(">   Quoted. Tail.\n"), [(1, 11)])


class NoFalsePositiveTest(unittest.TestCase):
    """Everything the check must stay quiet about."""

    def test_one_sentence_per_line(self):
        self.assertEqual(violations("The first one.\nThe second one.\n"), [])

    def test_trailing_whitespace_after_the_terminator(self):
        self.assertEqual(violations("A sentence.   \nAnother one.\n"), [])

    def test_abbreviations(self):
        for text in (
            "Use a tool, e.g. this one, when needed.",
            "That is, i.e. exactly this.",
            "Terraform, Markdown, etc. are all covered.",
            "Compare this vs. that one.",
            "It costs approx. 5 minutes.",
            "Released Jan. 2026 as planned.",
            "Ask Dr. Smith about it.",
        ):
            with self.subTest(text=text):
                self.assertEqual(violations(text + "\n"), [])

    def test_initialisms_and_initials(self):
        for text in (
            "The U.S. Government publishes it.",
            "It runs at 9 a.m. Monday to Friday.",
            "Named after J. R. R. Tolkien.",
        ):
            with self.subTest(text=text):
                self.assertEqual(violations(text + "\n"), [])

    def test_lowercase_after_the_terminator_is_not_a_sentence_start(self):
        # An abbreviation nobody listed still stays quiet, because what follows
        # is lowercase.
        self.assertEqual(violations("It needs approx. five minutes to run.\n"), [])

    def test_ellipsis(self):
        self.assertEqual(violations("It trails off... And so does this.\n"), [])

    def test_decimals_and_versions(self):
        self.assertEqual(violations("Pi is 3.14 and that is that.\n"), [])
        self.assertEqual(violations("Pin the workflow at v1.2 for now.\n"), [])

    def test_ordered_list_markers_are_not_sentence_ends(self):
        self.assertEqual(violations("1. First item\n2. Second item\n"), [])

    def test_atx_headings(self):
        self.assertEqual(violations("# A heading. With a tail.\n\nClean prose.\n"), [])

    def test_setext_headings(self):
        self.assertEqual(violations("A heading. With a tail.\n===\n\nClean prose.\n"), [])
        self.assertEqual(violations("A heading. With a tail.\n---\n\nClean prose.\n"), [])

    def test_fenced_code(self):
        self.assertEqual(
            violations(
                """
                Prose above.

                ```python
                x = 1  # Set it. Then use it.
                ```

                Prose below.
                """
            ),
            [],
        )

    def test_tilde_fence_and_a_longer_closing_fence(self):
        self.assertEqual(
            violations(
                """
                ~~~
                Do this. Then that.
                ~~~~

                Clean prose.
                """
            ),
            [],
        )

    def test_fenced_code_inside_a_list_item(self):
        self.assertEqual(
            violations(
                """
                - An item.

                  ```sh
                  echo one. echo Two.
                  ```
                """
            ),
            [],
        )

    def test_indented_code_block(self):
        self.assertEqual(
            violations(
                """
                Prose above.

                    run this. Then That.

                Prose below.
                """
            ),
            [],
        )

    def test_list_continuation_is_not_mistaken_for_indented_code(self):
        self.assertEqual(
            violations(
                """
                - An item.

                  A continuation paragraph. With a tail.
                """
            ),
            [(3, 27)],
        )

    def test_tables(self):
        self.assertEqual(
            violations(
                """
                | Column | Purpose |
                | --- | --- |
                | One. | Does a thing. And another. |

                Clean prose.
                """
            ),
            [],
        )

    def test_frontmatter(self):
        self.assertEqual(
            violations(
                """
                ---
                title: A title. With a tail.
                ---

                Clean prose.
                """
            ),
            [],
        )

    def test_unclosed_leading_delimiter_is_a_thematic_break_not_frontmatter(self):
        self.assertEqual(violations("---\n\nProse here. And more.\n"), [(3, 11)])

    def test_html_block_and_comment(self):
        self.assertEqual(
            violations(
                """
                <!--
                A comment. With a tail.
                -->

                <div>
                Inside HTML. With a tail.
                </div>
                """
            ),
            [],
        )

    def test_code_spans(self):
        self.assertEqual(violations("Run `git commit. Then push` as one command.\n"), [])
        self.assertEqual(violations("The file ``a.md. b.md`` is odd.\n"), [])

    def test_link_destinations_and_autolinks(self):
        self.assertEqual(violations("See [the docs](https://example.com/a. Then) here.\n"), [])
        self.assertEqual(violations("See <https://example.com/a.%20Then> here.\n"), [])

    def test_link_reference_definitions(self):
        self.assertEqual(violations("[ref]: https://example.com/a. Then\n"), [])

    def test_escaped_terminator_is_a_literal_not_a_sentence_end(self):
        # `\.` is how you write a dot that Markdown must not read as syntax; it
        # is deliberately ambiguous as a sentence end, so the check stays quiet.
        self.assertEqual(violations("A literal dot\\. Then more.\n"), [])


class DirectiveTest(unittest.TestCase):
    """The `<!-- sembr-* -->` suppression comments."""

    def test_disable_file(self):
        self.assertEqual(violations("<!-- sembr-disable-file -->\n\nOne. Two.\n"), [])

    def test_disable_next_line(self):
        self.assertEqual(
            violations("<!-- sembr-disable-next-line -->\nOne. Two.\n\nThree. Four.\n"),
            [(4, 6)],
        )

    def test_disable_and_enable_range(self):
        self.assertEqual(
            violations(
                """
                <!-- sembr-disable -->

                One. Two.

                <!-- sembr-enable -->

                Three. Four.
                """
            ),
            [(7, 6)],
        )


class FindingTest(unittest.TestCase):
    def test_message_quotes_both_sides_of_the_break(self):
        finding = sembr_check.check_text("The first one. The second one.\n")[0]
        self.assertIn("The first one.", finding.message)
        self.assertIn("The second one.", finding.message)

    def test_path_is_carried_through(self):
        finding = sembr_check.check_text("One. Two.\n", path="docs/x.md")[0]
        self.assertEqual(finding.path, "docs/x.md")


class CollectFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cwd = os.getcwd()
        self.addCleanup(os.chdir, self.cwd)
        for path in (
            "docs/a.md",
            "docs/nested/b.md",
            "vendor/c.md",
            "node_modules/d.md",
            ".github/e.md",
        ):
            full = os.path.join(self.tmp.name, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8") as handle:
                handle.write("Clean prose.\n")
        os.chdir(self.tmp.name)

    def test_recursive_glob_reaches_dot_directories_but_not_node_modules(self):
        self.assertEqual(
            sembr_check.collect_files(["**/*.md"], []),
            [".github/e.md", "docs/a.md", "docs/nested/b.md", "vendor/c.md"],
        )

    def test_ignore_glob(self):
        self.assertEqual(
            sembr_check.collect_files(["**/*.md"], ["vendor/**", ".github"]),
            ["docs/a.md", "docs/nested/b.md"],
        )

    def test_ignore_a_bare_directory(self):
        self.assertEqual(
            sembr_check.collect_files(["**/*.md"], ["docs", ".github"]), ["vendor/c.md"]
        )

    def test_explicit_glob_narrows_the_tree(self):
        self.assertEqual(sembr_check.collect_files(["docs/*.md"], []), ["docs/a.md"])


class CommandLineTest(unittest.TestCase):
    """End-to-end: exit status and both output formats."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, body):
        path = os.path.join(self.tmp.name, name)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(body)
        return path

    def run_check(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            cwd=self.tmp.name,
            capture_output=True,
            text=True,
        )

    def test_clean_tree_exits_zero(self):
        self.write("clean.md", "One sentence per line.\nAnd another.\n")
        result = self.run_check("**/*.md")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("no violations", result.stderr)

    def test_violation_exits_one_with_a_locatable_message(self):
        self.write("bad.md", "One. Two.\n")
        result = self.run_check("**/*.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad.md:1:4:", result.stdout)

    def test_github_format_emits_an_annotation(self):
        self.write("bad.md", "One. Two.\n")
        result = self.run_check("--format", "github", "**/*.md")
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error file=bad.md,line=1,col=4::", result.stdout)

    def test_github_format_escapes_commas_in_the_message(self):
        # A raw comma would end the annotation's property list early, so the
        # rest of the message would be parsed as `file=`/`line=` properties.
        self.write("bad.md", "One, and two. Three, and four.\n")
        result = self.run_check("--format", "github", "**/*.md")
        message = result.stdout.split("::", 2)[2]
        self.assertIn("%2C", message)
        self.assertNotIn(",", message)

    def test_ignore_flag_is_honoured(self):
        self.write("bad.md", "One. Two.\n")
        result = self.run_check("--ignore", "bad.md", "**/*.md")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_default_glob_is_the_whole_tree(self):
        self.write("bad.md", "One. Two.\n")
        self.assertEqual(self.run_check().returncode, 1)


if __name__ == "__main__":
    unittest.main()
