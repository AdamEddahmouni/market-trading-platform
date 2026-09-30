"""Final Screener closure: compound surnames and redistricted seats resolve only on official term evidence.

The registry is SYNTHETIC (``congress-legislators`` layout, fictitious Z9 ids). The two shapes come from the
S14 owner acceptance: the House index files "April McClain" / "Delaney" for a registry surname
"McClain Delaney", and still states a member's pre-redistricting district (GA-06 for a GA-07 member).
"""

from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr.identity import (  # noqa: E402
    MemberResolver,
    OfficialRegistry,
    house_identity,
)

FILED = date(2026, 3, 10)
REGISTRY = [
    {"id": {"bioguide": "Z910001"}, "name": {"first": "April", "middle": "Lynn", "last": "McClain Delaney",
                                            "official_full": "April McClain Delaney"},
     "terms": [{"type": "rep", "start": "2025-01-03", "end": "2027-01-03", "state": "MD", "district": 6}]},
    {"id": {"bioguide": "Z910002"}, "name": {"first": "Rich", "middle": "Dean", "last": "Moved",
                                            "official_full": "Richard Moved"},
     "terms": [{"type": "rep", "start": "2023-01-03", "end": "2025-01-03", "state": "GA", "district": 6},
               {"type": "rep", "start": "2025-01-03", "end": "2027-01-03", "state": "GA", "district": 7}]},
    {"id": {"bioguide": "Z910003"}, "name": {"first": "Lucy", "last": "Seatholder", "official_full": "Lucy Seatholder"},
     "terms": [{"type": "rep", "start": "2025-01-03", "end": "2027-01-03", "state": "GA", "district": 6}]},
    {"id": {"bioguide": "Z910004"}, "name": {"first": "Paul", "last": "Delaney", "official_full": "Paul Delaney"},
     "terms": [{"type": "rep", "start": "2025-01-03", "end": "2027-01-03", "state": "MD", "district": 8}]},
]


def resolve(*identities):
    resolver = MemberResolver(OfficialRegistry.from_legislators(REGISTRY, source="synthetic"))
    out = resolver.resolve(identities)
    return [out[identity.key] for identity in identities]


def rep(first, last, seat, filed=FILED):
    return house_identity(first, last, "", "Hon.", seat, filed)


class CompoundSurnameTests(unittest.TestCase):
    def test_index_split_of_a_compound_surname_resolves_on_seat_term_and_given_name(self):
        (item,) = resolve(rep("April McClain", "Delaney", "MD06"))
        self.assertEqual((item.resolution, item.canonical_member_id, item.basis),
                         ("OFFICIAL_ID", "BIOGUIDE:Z910001", "REGISTRY_SEAT_TERM_AND_COMPOUND_SURNAME"))
        self.assertEqual(item.canonical_name, "April McClain Delaney")

    def test_the_compound_rule_needs_the_given_name(self):
        (item,) = resolve(rep("Joan McClain", "Delaney", "MD06"))
        self.assertNotEqual(item.resolution, "OFFICIAL_ID")

    def test_a_bare_shared_surname_in_another_seat_is_not_merged(self):
        # "Delaney" alone does not spell "McClain Delaney"; MD-08's Delaney is a different seat.
        (item,) = resolve(rep("April", "Delaney", "MD06"))
        self.assertNotEqual(item.resolution, "OFFICIAL_ID")


class PriorSeatTests(unittest.TestCase):
    def test_an_earlier_district_resolves_to_the_redistricted_member(self):
        (item,) = resolve(rep("Richard", "Moved", "GA06"))
        self.assertEqual((item.resolution, item.canonical_member_id, item.basis),
                         ("OFFICIAL_ID", "BIOGUIDE:Z910002", "REGISTRY_PRIOR_SEAT_TERM_AND_NAME"))
        self.assertEqual(item.notes, ("SOURCE_SEAT_IS_AN_EARLIER_TERM",))

    def test_the_current_holder_of_the_stated_seat_still_resolves_directly(self):
        (item,) = resolve(rep("Lucy", "Seatholder", "GA06"))
        self.assertEqual((item.canonical_member_id, item.basis), ("BIOGUIDE:Z910003", "REGISTRY_SEAT_TERM_AND_SURNAME"))

    def test_prior_seat_needs_the_given_name_and_a_current_term_in_the_state(self):
        for identity in (rep("Mary", "Moved", "GA06"),                     # given name disagrees
                         rep("Richard", "Moved", "GA06", date(2024, 6, 1)),  # before the move: GA-06 is his seat
                         rep("Richard", "Moved", "GA06", date(2027, 6, 1))):  # after every term: not serving
            with self.subTest(identity.source_name, filed=identity.filed_on):
                (item,) = resolve(identity)
                if identity.filed_on == date(2024, 6, 1):
                    self.assertEqual(item.basis, "REGISTRY_SEAT_TERM_AND_SURNAME")   # the ordinary seat rule
                else:
                    self.assertNotEqual(item.resolution, "OFFICIAL_ID")

    def test_official_full_given_name_is_evidence_but_similarity_is_not(self):
        (official,) = resolve(rep("Rich", "Moved", "GA06"))                # the registry's own first name
        self.assertEqual(official.canonical_member_id, "BIOGUIDE:Z910002")
        (similar,) = resolve(rep("Ricardo", "Moved", "GA06"))
        self.assertNotEqual(similar.resolution, "OFFICIAL_ID")


if __name__ == "__main__":
    unittest.main()
