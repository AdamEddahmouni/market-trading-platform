"""BUILD 10 inference job persistence tests."""

from __future__ import annotations

import unittest

from market_platform_foundation.intelligence.persistence import (
    InMemoryIntelligenceRepository,
    RepositoryConflictError,
    RepositoryPutResult,
)
from tests.intelligence.test_scheduler_contracts import sample_job


class InferenceJobPersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryIntelligenceRepository()

    def test_put_get_round_trip(self) -> None:
        job = sample_job()
        self.assertEqual(self.repo.put_inference_job(job), RepositoryPutResult.INSERTED)
        stored = self.repo.get_inference_job(job.job_id)
        assert stored is not None
        self.assertEqual(stored, job)

    def test_idempotent_same_content(self) -> None:
        job = sample_job()
        self.assertEqual(self.repo.put_inference_job(job), RepositoryPutResult.INSERTED)
        self.assertEqual(self.repo.put_inference_job(job), RepositoryPutResult.ALREADY_PRESENT)

    def test_conflict_different_content(self) -> None:
        import dataclasses

        job = sample_job()
        self.repo.put_inference_job(job)
        changed = dataclasses.replace(job, batch_key="other-batch")
        with self.assertRaises(RepositoryConflictError):
            self.repo.put_inference_job(changed)
