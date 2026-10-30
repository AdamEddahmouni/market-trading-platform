"""A source release keeps the collector manifest consistent and does not bless other hashes."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.release_candidate.apply_release import apply, rollback, verify


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class CollectorManifestReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.target = root / 'app'
        self.collector = root / 'collector'
        self.rc = root / 'rc'
        self.preimage = root / 'preimage'
        self.target.mkdir()
        (self.target / 'tools' / 'ui1').mkdir(parents=True)
        (self.target / 'tools' / 'ui1' / 'run_ui_api.py').write_text('print("stub")\n', encoding='utf-8')
        self.listed = 'src/market_platform_foundation/ui_api/paper_projections.py'
        self.other = 'src/market_platform_foundation/ui_api/untouched.py'
        self.unlisted = 'src/market_platform_foundation/ui_api/unlisted.py'
        self.old = b'OLD_PROJECTION\n'
        self.new = b'NEW_PROJECTION\n'
        self.untouched = b'UNTOUCHED\n'
        self.unlisted_new = b'UNLISTED\n'
        for rel, data in ((self.listed, self.old), (self.other, self.untouched)):
            path = self.target / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.collector.mkdir()
        self.manifest_path = self.collector / 'RELEASE_MANIFEST.json'
        self.original = {
            'release': 'previous',
            'commit': '1' * 40,
            'files': {self.listed: digest(self.old), self.other: digest(self.untouched)},
            'carry_close_hotfix': {'file': self.listed, 'sha256': digest(self.old)},
        }
        self.manifest_path.write_text(json.dumps(self.original, indent=2) + '\n', encoding='utf-8')
        self.original_bytes = self.manifest_path.read_bytes()
        for rel, data in ((self.listed, self.new), (self.unlisted, self.unlisted_new)):
            path = self.rc / 'delta' / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        self.release = {
            'release': 'test-release',
            'commit': '2' * 40,
            'files': [
                {'path': self.listed, 'sha256': digest(self.new), 'serving_preimage_sha256': digest(self.old), 'status': 'replaced'},
                {'path': self.unlisted, 'sha256': digest(self.unlisted_new), 'serving_preimage_sha256': None, 'status': 'added'},
            ],
            'preserve': [{'path': self.other, 'sha256': digest(self.untouched)}],
            'conflicts': [],
        }

    def listed_files_match(self):
        files = json.loads(self.manifest_path.read_text(encoding='utf-8'))['files']
        return all(digest((self.target / name).read_bytes()) == expected for name, expected in files.items())

    def test_apply_updates_only_the_listed_hash_and_rollback_restores_both(self):
        self.assertTrue(self.listed_files_match())
        self.assertEqual(verify(self.target, self.release, self.manifest_path), [])

        record = apply(self.target, self.preimage, self.release, rc=self.rc, collector_manifest=self.manifest_path)

        self.assertEqual((self.target / self.listed).read_bytes(), self.new)
        self.assertEqual((self.target / self.unlisted).read_bytes(), self.unlisted_new)
        self.assertEqual((self.target / self.other).read_bytes(), self.untouched)
        body = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(body['files'][self.listed], digest(self.new))
        self.assertEqual(body['files'][self.other], digest(self.untouched))
        self.assertNotIn(self.unlisted, body['files'])
        self.assertEqual(body['carry_close_hotfix']['sha256'], digest(self.old))
        self.assertEqual(body['release_applications'][-1]['files'], [self.listed])
        self.assertEqual(record['collector_manifest']['updated'], [self.listed])
        self.assertTrue(self.listed_files_match())
        self.assertTrue(any(item.startswith('PREIMAGE_CHANGED') for item in verify(self.target, self.release, self.manifest_path)))

        outcome = rollback(self.target, self.preimage, self.release)

        self.assertTrue(outcome['tree_matches_pre_release_manifest'])
        self.assertEqual((self.target / self.listed).read_bytes(), self.old)
        self.assertFalse((self.target / self.unlisted).exists())
        self.assertEqual(self.manifest_path.read_bytes(), self.original_bytes)
        self.assertTrue(self.listed_files_match())

    def test_a_manifest_that_does_not_name_the_preimage_is_refused(self):
        body = json.loads(self.original_bytes)
        body['files'][self.listed] = 'c' * 64
        self.manifest_path.write_text(json.dumps(body), encoding='utf-8')
        before = self.manifest_path.read_bytes()

        problems = verify(self.target, self.release, self.manifest_path)
        self.assertIn(f'COLLECTOR_MANIFEST_DIVERGED {self.listed}', problems)
        with self.assertRaises(RuntimeError) as caught:
            apply(self.target, self.preimage, self.release, rc=self.rc, collector_manifest=self.manifest_path)

        self.assertIn('COLLECTOR_MANIFEST_DIVERGED', str(caught.exception))
        self.assertEqual((self.target / self.listed).read_bytes(), self.old)
        self.assertEqual(self.manifest_path.read_bytes(), before)
        self.assertFalse(self.preimage.exists())

    def test_partial_apply_leaves_the_manifest_until_rollback_restores_the_source(self):
        listed_only = {**self.release, 'files': [self.release['files'][0], {
            'path': self.other, 'sha256': digest(b'REPLACED_OTHER\n'), 'serving_preimage_sha256': digest(self.untouched), 'status': 'replaced'}]}
        (self.rc / 'delta' / self.other).write_bytes(b'REPLACED_OTHER\n')

        apply(self.target, self.preimage, listed_only, rc=self.rc, entries=[listed_only['files'][0]], collector_manifest=self.manifest_path)

        self.assertEqual((self.target / self.listed).read_bytes(), self.new)
        self.assertEqual(self.manifest_path.read_bytes(), self.original_bytes)
        self.assertFalse(self.listed_files_match())
        outcome = rollback(self.target, self.preimage, listed_only)
        self.assertTrue(outcome['tree_matches_pre_release_manifest'])
        self.assertEqual((self.target / self.listed).read_bytes(), self.old)
        self.assertEqual(self.manifest_path.read_bytes(), self.original_bytes)
        self.assertTrue(self.listed_files_match())

    def test_incompatible_source_preimage_is_rejected(self):
        (self.target / self.listed).write_bytes(b'SOME_OTHER_BYTES\n')

        problems = verify(self.target, self.release, self.manifest_path)

        self.assertTrue(any(item.startswith(f'PREIMAGE_CHANGED {self.listed}') for item in problems))


if __name__ == '__main__':
    unittest.main()
