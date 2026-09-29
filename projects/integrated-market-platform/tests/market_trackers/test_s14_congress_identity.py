"""S14 congressional member identity: evidence-based canonical ids, never name-similarity merges.

The registry here is SYNTHETIC, in the ``congress-legislators`` JSON layout the resolver
reads; its Bioguide-shaped ids (Z9xxxxx) are fictitious. Member names reuse spellings
seen in the House Clerk index where the S12 limitation came from.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.congressional_ptr.identity import (  # noqa: E402
    MemberResolver,
    OfficialRegistry,
    SourceIdentity,
    house_identity,
    registry_from_env,
    split_full_name,
    split_name,
)


def rep(first, last, seat, filed, suffix="", prefix=""):
    return house_identity(first, last, suffix, prefix, seat, filed)


def sen(name, filed, state=None):
    return SourceIdentity("SENATE", "senate_efd", name, split_full_name(name), filed, state)


REGISTRY = [
    {"id": {"bioguide": "Z900001"}, "name": {"first": "John", "middle": "J.", "last": "McGuire", "suffix": "III",
                                            "official_full": "John J. McGuire III"},
     "terms": [{"type": "rep", "start": "2025-01-03", "end": "2027-01-03", "state": "VA", "district": 5}]},
    {"id": {"bioguide": "Z900002"}, "name": {"first": "Donald", "middle": "M.", "last": "Payne", "official_full": "Donald M. Payne"},
     "terms": [{"type": "rep", "start": "2011-01-05", "end": "2012-03-06", "state": "NJ", "district": 10}]},
    {"id": {"bioguide": "Z900003"}, "name": {"first": "Donald", "middle": "M.", "last": "Payne", "suffix": "Jr.",
                                            "official_full": "Donald M. Payne, Jr."},
     "terms": [{"type": "rep", "start": "2012-11-15", "end": "2013-01-03", "state": "NJ", "district": 10}]},
    {"id": {"bioguide": "Z900004"}, "name": {"first": "Alexandra", "last": "Mover", "official_full": "Alexandra Mover"},
     "terms": [{"type": "rep", "start": "2023-01-03", "end": "2025-01-03", "state": "OH", "district": 7},
               {"type": "sen", "start": "2025-01-03", "end": "2031-01-03", "state": "OH"}]},
    {"id": {"bioguide": "Z900005"}, "name": {"first": "Thomas", "last": "Twin", "nickname": "Tom", "official_full": "Thomas Twin"},
     "terms": [{"type": "sen", "start": "2021-01-03", "end": "2027-01-03", "state": "TX"}]},
    {"id": {"bioguide": "Z900006"}, "name": {"first": "Thomas", "last": "Twin", "official_full": "Thomas Twin"},
     "terms": [{"type": "sen", "start": "2023-01-03", "end": "2029-01-03", "state": "MT"}]},
    {"id": {"bioguide": "Z900007"}, "name": {"first": "Josh", "last": "Gottheimer", "official_full": "Josh Gottheimer"},
     "terms": [{"type": "rep", "start": "2025-01-03", "end": "2027-01-03", "state": "NJ", "district": 5}]},
    {"id": {"bioguide": "bad"}, "name": {"first": "No", "last": "Id"}, "terms": []},   # no official id: ignored
]


class NameTests(unittest.TestCase):
    def test_honorifics_middles_and_suffixes(self):
        name = split_name("John J Mr", "McGuire", "III")
        self.assertEqual((name.given, name.middles, name.family, name.suffix), ("john", ("j",), "mcguire", "iii"))
        self.assertEqual(name.display, "John J McGuire III")
        self.assertEqual(split_name("Josh", "Gottheimer", prefix="Hon.").honorifics, ("Hon",))
        self.assertEqual(split_name("Richard Dean Dr", "McCormick").display, "Richard Dean McCormick")
        self.assertEqual(split_full_name("Tuberville, Tommy").family, "tuberville")
        self.assertEqual(split_full_name("Donald M. Payne Jr.").suffix, "jr")
        self.assertEqual(split_name("José", "Sánchez").family, "sanchez")


class SeatEvidenceTests(unittest.TestCase):
    """No registry: the House seat is the evidence."""

    def resolve(self, *identities):
        resolved = MemberResolver().resolve(identities)
        return [resolved[item.key] for item in identities]

    def test_same_member_two_spellings_same_seat(self):
        a, b = self.resolve(rep("Richard Dean Dr", "McCormick", "GA07", date(2026, 8, 1)),
                            rep("Richard", "McCormick", "GA07", date(2026, 9, 1)))
        self.assertEqual(a.canonical_member_id, b.canonical_member_id)
        self.assertEqual((a.resolution, a.basis), ("SEAT_AND_NAME", "SAME_HOUSE_SEAT_SAME_GIVEN_SURNAME_SUFFIX"))
        self.assertEqual(a.canonical_name, "Richard Dean McCormick")
        self.assertEqual(a.source_names, ("Richard Dean Dr McCormick", "Richard McCormick"))

    def test_honorific_noise_merges_on_seat(self):
        a, b = self.resolve(rep("Josh", "Gottheimer", "NJ05", date(2026, 9, 14), prefix="Hon."),
                            rep("Josh", "Gottheimer", "NJ05", date(2026, 8, 1), prefix="Mr."))
        self.assertEqual(a.canonical_member_id, b.canonical_member_id)

    def test_suffix_variant_is_not_merged_without_official_evidence(self):
        a, b = self.resolve(rep("John", "McGuire", "VA05", date(2026, 8, 1)),
                            rep("John J Mr", "McGuire", "VA05", date(2026, 9, 1), suffix="III"))
        self.assertNotEqual(a.canonical_member_id, b.canonical_member_id)
        self.assertIn("SUFFIX_VARIANT_IN_SAME_SEAT_UNVERIFIED", a.notes)
        self.assertIn("SUFFIX_VARIANT_IN_SAME_SEAT_UNVERIFIED", b.notes)

    def test_conflicting_middle_initials_are_ambiguous(self):
        a, b, c = self.resolve(rep("Richard A", "Smith", "NY03", date(2026, 8, 1)),
                               rep("Richard B", "Smith", "NY03", date(2026, 8, 2)),
                               rep("Richard", "Smith", "NY03", date(2026, 8, 3)))
        self.assertEqual({a.resolution, b.resolution, c.resolution}, {"AMBIGUOUS"})
        self.assertEqual(len({a.canonical_member_id, b.canonical_member_id, c.canonical_member_id}), 3)

    def test_same_name_different_districts_are_different_people(self):
        a, b = self.resolve(rep("John", "Smith", "NY03", date(2026, 8, 1)), rep("John", "Smith", "NY04", date(2026, 8, 1)))
        self.assertNotEqual(a.canonical_member_id, b.canonical_member_id)

    def test_different_given_names_same_seat_stay_apart(self):
        a, b = self.resolve(rep("Rich", "McCormick", "GA07", date(2026, 8, 1)), rep("Richard", "McCormick", "GA07", date(2026, 8, 1)))
        self.assertNotEqual(a.canonical_member_id, b.canonical_member_id)   # nicknames need official evidence

    def test_unknown_and_senate_without_registry(self):
        unknown, = self.resolve(rep("", "", "", None))
        self.assertEqual((unknown.resolution, unknown.basis), ("UNRESOLVED", "SOURCE_NAME_INCOMPLETE"))
        a, b = self.resolve(sen("Jane Q Example", date(2026, 1, 30)), sen("Jane Example", date(2026, 2, 1)))
        self.assertEqual((a.resolution, b.resolution), ("UNRESOLVED", "UNRESOLVED"))
        self.assertNotEqual(a.canonical_member_id, b.canonical_member_id)   # name similarity alone never merges


class OfficialRegistryTests(unittest.TestCase):
    def setUp(self):
        self.resolver = MemberResolver(OfficialRegistry.from_legislators(REGISTRY, source="synthetic"))

    def resolve(self, *identities):
        resolved = self.resolver.resolve(identities)
        return [resolved[item.key] for item in identities]

    def test_entries_without_official_id_are_ignored(self):
        self.assertEqual(len(self.resolver.registry.members), 7)

    def test_suffix_variants_resolve_by_seat_term(self):
        a, b = self.resolve(rep("John", "McGuire", "VA05", date(2026, 8, 1)),
                            rep("John J Mr", "McGuire", "VA05", date(2026, 9, 1), suffix="III"))
        self.assertEqual((a.canonical_member_id, b.canonical_member_id), ("BIOGUIDE:Z900001", "BIOGUIDE:Z900001"))
        self.assertEqual((a.resolution, a.basis, a.canonical_name), ("OFFICIAL_ID", "REGISTRY_SEAT_TERM_AND_SURNAME", "John J. McGuire III"))
        self.assertEqual(a.official_ids, {"bioguide": "Z900001"})
        self.assertEqual(a.source_names, ("John J Mr McGuire III", "John McGuire"))

    def test_same_name_successor_in_the_same_seat_is_a_different_person(self):
        early, late = self.resolve(rep("Donald M", "Payne", "NJ10", date(2012, 2, 1)),
                                   rep("Donald M", "Payne", "NJ10", date(2012, 12, 1), suffix="Jr"))
        self.assertEqual((early.canonical_member_id, late.canonical_member_id), ("BIOGUIDE:Z900002", "BIOGUIDE:Z900003"))

    def test_filing_outside_any_term_is_not_forced(self):
        gap, = self.resolve(rep("Donald M", "Payne", "NJ10", date(2012, 6, 1)))   # vacancy between the two terms
        self.assertEqual(gap.resolution, "SEAT_AND_NAME")                         # seat evidence only, no official id
        self.assertFalse(gap.canonical_member_id.startswith("BIOGUIDE:"))

    def test_chamber_transition_keeps_one_identity(self):
        house, senator = self.resolve(rep("Alexandra", "Mover", "OH07", date(2024, 6, 1)), sen("Alexandra Mover", date(2026, 3, 1)))
        self.assertEqual((house.canonical_member_id, senator.canonical_member_id), ("BIOGUIDE:Z900004", "BIOGUIDE:Z900004"))
        self.assertEqual((house.chamber, senator.chamber), ("HOUSE", "SENATE"))

    def test_senate_same_surname_needs_the_given_name_and_can_stay_ambiguous(self):
        tom, = self.resolve(sen("Tom Twin", date(2026, 3, 1), state="TX"))
        self.assertEqual(tom.canonical_member_id, "BIOGUIDE:Z900005")       # state narrows to one senator
        both, = self.resolve(sen("Thomas Twin", date(2026, 3, 1)))
        self.assertEqual((both.resolution, both.basis), ("AMBIGUOUS", "REGISTRY_MULTIPLE_CANDIDATES"))
        self.assertEqual(both.notes, ("CANDIDATE:Z900005", "CANDIDATE:Z900006"))

    def test_surname_must_agree_with_the_seat_holder(self):
        other, = self.resolve(rep("Pat", "Stranger", "VA05", date(2026, 8, 1)))
        self.assertNotEqual(other.resolution, "OFFICIAL_ID")

    def test_registry_from_env_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "legislators.json"
            path.write_text(json.dumps(REGISTRY))
            registry = registry_from_env({"IMP_CONGRESS_LEGISLATORS_PATH": str(path)})
            self.assertEqual(len(registry.members), 7)
            self.assertIsNone(registry_from_env({}))


if __name__ == "__main__":
    unittest.main()
