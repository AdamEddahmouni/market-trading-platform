import unittest

from tools.monorepo_guard import GuardError, validate_manifest_data, validate_snapshot_entries


class MonorepoGuardTests(unittest.TestCase):
    def test_current_workspace_contract_is_valid(self):
        manifest = {
            "version": 1,
            "parent": {
                "repository": "AdamEddahmouni/market-trading-platform",
                "visibility": "private",
            },
            "projects": [
                {
                    "id": "integrated-platform",
                    "source_path": "integrated-market-platform",
                    "snapshot_path": "projects/integrated-market-platform",
                    "source_remote": "https://github.com/owner/repo.git",
                    "source_ref": "codex/paper-accounting-risk-foundation",
                    "source_commit": "6308fcfce9e71ffaeaf22f24743a03c81691e0c6",
                    "expected_visibility": "private",
                    "source_policy": "unchanged",
                },
                {
                    "id": "short-squeeze",
                    "source_path": "short-squeeze-project",
                    "snapshot_path": "projects/short-squeeze-project",
                    "source_remote": "https://github.com/owner/repo.git",
                    "source_ref": "phase/3e-historical-acquisition",
                    "source_commit": "0b40834" + "0" * 33,
                    "expected_visibility": "public",
                    "source_policy": "unchanged",
                },
            ],
        }

        self.assertEqual(validate_manifest_data(manifest), [])

    def test_manifest_rejects_snapshot_outside_projects(self):
        manifest = {
            "version": 1,
            "parent": {"repository": "owner/repo", "visibility": "private"},
            "projects": [
                {
                    "id": "example",
                    "source_path": "example",
                    "snapshot_path": "example",
                    "source_ref": "main",
                    "source_commit": "a" * 40,
                    "expected_visibility": "private",
                    "source_policy": "unchanged",
                }
            ],
        }

        errors = validate_manifest_data(manifest)

        self.assertIn("snapshot_path must be under projects/", errors)

    def test_snapshot_entries_reject_embedded_gitlinks(self):
        with self.assertRaises(GuardError):
            validate_snapshot_entries(
                [
                    ("100644", "projects/example/README.md"),
                    ("160000", "projects/example/nested-repository"),
                ]
            )


if __name__ == "__main__":
    unittest.main()
