import unittest

from tools.generate_history_ledger import (
    parse_commit_object,
    rationale_status,
    render_repository_markdown,
)


class HistoryLedgerTests(unittest.TestCase):
    def test_parse_commit_object_preserves_identity_and_message(self):
        raw = (
            b"tree " + b"a" * 40 + b"\n"
            b"parent " + b"b" * 40 + b"\n"
            b"author Ada Example <ada@example.com> 1754000000 -0400\n"
            b"committer Ada Example <ada@example.com> 1754000100 -0400\n"
            b"\n"
            b"feat: establish audit trail\n"
            b"\n"
            b"Document why the repository boundary exists.\n"
        )

        record = parse_commit_object(raw)

        self.assertEqual(record["parents"], ["b" * 40])
        self.assertEqual(record["author"]["name"], "Ada Example")
        self.assertEqual(record["subject"], "feat: establish audit trail")
        self.assertIn("repository boundary", record["body"])

    def test_rationale_status_does_not_invent_missing_context(self):
        self.assertEqual(
            rationale_status("chore: update lockfile", ""),
            "commit-subject-only",
        )
        self.assertEqual(
            rationale_status("feat: add audit ledger", "Explains the reason."),
            "commit-subject-and-body",
        )

    def test_repository_markdown_groups_commits_by_date(self):
        records = [
            {
                "commit": "a" * 40,
                "short_commit": "a" * 12,
                "committed_at": "2026-09-03T12:00:00-04:00",
                "committer": {"timestamp": "2026-09-03T12:00:00-04:00"},
                "author": {"name": "Ada Example", "timestamp": "2026-09-03T12:00:00-04:00"},
                "subject": "feat: newer work",
                "body": "",
                "rationale_status": "commit-subject-only",
                "refs": ["refs/heads/main"],
            },
            {
                "commit": "b" * 40,
                "short_commit": "b" * 12,
                "committed_at": "2026-08-01T12:00:00-04:00",
                "committer": {"timestamp": "2026-08-01T12:00:00-04:00"},
                "author": {"name": "Ada Example", "timestamp": "2026-08-01T12:00:00-04:00"},
                "subject": "docs: initial work",
                "body": "Why it started.",
                "rationale_status": "commit-subject-and-body",
                "refs": [],
            },
        ]

        rendered = render_repository_markdown("example", records)

        self.assertLess(rendered.index("2026-08-01"), rendered.index("2026-09-03"))
        self.assertIn("Why it started.", rendered)
        self.assertIn("`" + "a" * 12 + "`", rendered)


if __name__ == "__main__":
    unittest.main()
