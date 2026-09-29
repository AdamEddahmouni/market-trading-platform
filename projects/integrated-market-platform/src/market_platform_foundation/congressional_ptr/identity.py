"""Congressional member identity (Screener S14): canonical ids without speculative merging.

Disclosure sources spell members differently (the House Clerk's index has produced
both "John McGuire" and "John J Mr McGuire III" for VA05). The source spelling is
provenance and is never overwritten; this module adds a canonical identity *beside* it,
and only on evidence:

1. ``OFFICIAL_ID`` — an operator-supplied registry keyed by official Bioguide ids with
   dated terms (the ``congress-legislators`` JSON layout). A House filing resolves when
   exactly one registry member held that seat on the filing date *and* the surname
   agrees; a Senate filing when exactly one senator serving on that date (in the stated
   state, if any) has that surname and a compatible given name. Terms make this
   point-in-time safe: a seat's successor, a district change, or a move between
   chambers resolves to the person who held the office on that date.
2. ``SEAT_AND_NAME`` (House only, no registry needed) — a House seat has one member at
   a time, so filings for the same seat whose names agree after removing honorifics and
   middle names/initials (same given name, same surname, same generational suffix) are
   one member. Conflicting middle initials make the whole group ``AMBIGUOUS``. A suffix
   present in one spelling and absent in another is *not* merged (a Jr. can succeed a
   parent in the same seat); it is noted as an unverified possible alias.
3. ``UNRESOLVED`` — everything else keeps an id derived from the exact source identity.
   Name similarity alone never merges two identities.
"""

from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

IDENTITY_VERSION = "congressional_ptr.identity/1.0.0"
REGISTRY_ENV = "IMP_CONGRESS_LEGISLATORS_PATH"
HONORIFICS = frozenset({"hon", "honorable", "the", "mr", "mrs", "ms", "miss", "dr", "rep", "representative", "sen",
                        "senator", "congressman", "congresswoman", "member"})
SUFFIXES = {"jr": "Jr.", "sr": "Sr.", "ii": "II", "iii": "III", "iv": "IV", "v": "V"}
_SEAT = re.compile(r"^([A-Z]{2})(\d{1,2}|AL)$")


def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")


def _tokens(text: str) -> list[str]:
    return [token for token in re.split(r"[\s,]+", _fold(text).replace(".", " ")) if token]


def _key(token: str) -> str:
    return re.sub(r"[^a-z\-]", "", token.lower())


@dataclass(frozen=True, slots=True)
class NameParts:
    """A source name split for comparison; ``display`` keeps the filer's capitalization."""

    given: str
    middles: tuple[str, ...]
    family: str
    suffix: str
    display: str
    honorifics: tuple[str, ...] = ()

    @property
    def middle_initials(self) -> str:
        return "".join(item[0] for item in self.middles if item)


def split_name(first: str, last: str, suffix: str = "", prefix: str = "") -> NameParts:
    """Normalize one source name. Honorifics are dropped wherever the source put them."""

    removed: list[str] = [token for token in _tokens(prefix) if _key(token) in HONORIFICS]
    first_tokens: list[str] = []
    found_suffix = _key(suffix).replace("-", "") if suffix else ""
    for token in _tokens(first):
        key = _key(token)
        if key in HONORIFICS:
            removed.append(token)
        elif key in SUFFIXES and first_tokens:
            found_suffix = found_suffix or key
        else:
            first_tokens.append(token)
    family_tokens: list[str] = []
    for token in _tokens(last):
        key = _key(token)
        if key in SUFFIXES and family_tokens:
            found_suffix = found_suffix or key
        elif key in HONORIFICS and not family_tokens:
            removed.append(token)
        else:
            family_tokens.append(token)
    found_suffix = found_suffix if found_suffix in SUFFIXES else ""
    given = _key(first_tokens[0]) if first_tokens else ""
    middles = tuple(_key(token) for token in first_tokens[1:] if _key(token))
    family = "".join(_key(token) for token in family_tokens)
    display = " ".join([*(first_tokens or []), *family_tokens, *([SUFFIXES[found_suffix]] if found_suffix else [])])
    return NameParts(given, middles, family, found_suffix, display, tuple(removed))


def split_full_name(full: str) -> NameParts:
    """Split a single-string name ("Hon. Josh Gottheimer", "Tuberville, Tommy")."""

    text = _fold(full).strip()
    if "," in text:
        family, _, rest = text.partition(",")
        rest_tokens = _tokens(rest)
        suffix = next((token for token in rest_tokens if _key(token) in SUFFIXES), "")
        return split_name(" ".join(token for token in rest_tokens if token != suffix), family, suffix)
    tokens = _tokens(text)
    suffix = ""
    if len(tokens) > 2 and _key(tokens[-1]) in SUFFIXES:
        suffix = tokens.pop()
    return split_name(" ".join(tokens[:-1]), tokens[-1] if tokens else "", suffix)


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """A member as one disclosure source names them; ``key`` is stable per source identity."""

    chamber: str                 # HOUSE / SENATE
    source: str                  # house_clerk / senate_efd
    source_name: str
    name: NameParts
    filed_on: date | None
    state: str | None = None
    district: str | None = None  # House seat number ("05", "AL"); None for the Senate
    source_member_id: str | None = None

    @property
    def seat(self) -> str | None:
        if self.chamber != "HOUSE" or not self.state or not self.district:
            return None
        return f"{self.state}{self.district}"

    @property
    def key(self) -> str:
        if self.source_member_id:
            return f"{self.source}:{self.source_member_id}"
        seat = self.seat or self.state or ""
        return f"{self.source}:{seat}:{_fold(self.source_name).strip().upper()}"


def house_identity(first: str, last: str, suffix: str, prefix: str, state_district: str, filed_on: date | None,
                   *, source_name: str | None = None) -> SourceIdentity:
    seat = (state_district or "").strip().upper()
    match = _SEAT.match(seat)
    state, district = (match.group(1), match.group(2).zfill(2) if match.group(2) != "AL" else "AL") if match else (None, None)
    name = split_name(first, last, suffix, prefix)
    shown = source_name or " ".join(part for part in (first, last, suffix) if part)
    return SourceIdentity("HOUSE", "house_clerk", shown, name, filed_on, state, district)


# ------------------------------------------------------------------ official registry
@dataclass(frozen=True, slots=True)
class RegistryTerm:
    chamber: str
    state: str
    district: str | None
    start: date
    end: date


@dataclass(frozen=True, slots=True)
class RegistryMember:
    bioguide: str
    official_name: str
    name: NameParts
    terms: tuple[RegistryTerm, ...]
    other_names: tuple[NameParts, ...] = ()

    def serving(self, chamber: str, on: date, state: str | None = None, district: str | None = None) -> bool:
        for term in self.terms:
            if term.chamber != chamber or not term.start <= on <= term.end:
                continue
            if state and term.state != state:
                continue
            if district and chamber == "HOUSE" and term.district != district:
                continue
            return True
        return False

    def family_names(self) -> set[str]:
        return {self.name.family, *(item.family for item in self.other_names)} - {""}


class OfficialRegistry:
    """Members keyed by Bioguide id with dated terms (``congress-legislators`` JSON layout)."""

    def __init__(self, members: Iterable[RegistryMember], *, source: str) -> None:
        self.members = tuple(members)
        self.source = source

    @classmethod
    def from_legislators(cls, payload: Any, *, source: str = "congress-legislators") -> OfficialRegistry:
        rows = payload if isinstance(payload, list) else []
        members: list[RegistryMember] = []
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            bioguide = str((row.get("id") or {}).get("bioguide") or "").strip()
            name = row.get("name") or {}
            if not re.fullmatch(r"[A-Z]\d{6}", bioguide) or not name.get("last"):
                continue  # entries without an official id or surname are not identity evidence
            terms = []
            for term in row.get("terms") or []:
                try:
                    start, end = date.fromisoformat(str(term["start"])), date.fromisoformat(str(term["end"]))
                except (KeyError, ValueError):
                    continue
                chamber = {"rep": "HOUSE", "sen": "SENATE"}.get(str(term.get("type")))
                if chamber is None:
                    continue
                district = term.get("district")
                district_text = None if chamber == "SENATE" else ("AL" if district in (0, "0", "AL") else f"{int(district):02d}")
                terms.append(RegistryTerm(chamber, str(term.get("state") or "").upper(), district_text, start, end))
            parts = split_name(" ".join(item for item in (name.get("first"), name.get("middle")) if item),
                               name["last"], name.get("suffix") or "")
            nicknames = tuple(split_name(nick, name["last"], name.get("suffix") or "")
                              for nick in [name.get("nickname")] if nick)
            official = name.get("official_full") or parts.display
            members.append(RegistryMember(bioguide, official, parts, tuple(terms), nicknames))
        return cls(members, source=source)

    @classmethod
    def from_paths(cls, paths: Iterable[str | Path]) -> OfficialRegistry:
        rows: list[Any] = []
        names = []
        for path in paths:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            rows.extend(payload if isinstance(payload, list) else [])
            names.append(Path(path).name)
        return cls.from_legislators(rows, source="congress-legislators:" + ",".join(names))

    def candidates(self, identity: SourceIdentity) -> list[RegistryMember]:
        if identity.filed_on is None:
            return []
        if identity.chamber == "HOUSE":
            if identity.seat is None:
                return []
            serving = [m for m in self.members if m.serving("HOUSE", identity.filed_on, identity.state, identity.district)]
            return [m for m in serving if identity.name.family in m.family_names()]
        serving = [m for m in self.members if m.serving("SENATE", identity.filed_on, identity.state)]
        by_family = [m for m in serving if identity.name.family in m.family_names()]
        if len(by_family) <= 1:
            return by_family
        # Two serving senators share the surname: the given name must also agree.
        return [m for m in by_family if identity.name.given in {m.name.given, *(n.given for n in m.other_names)}]


def registry_from_env(env: Mapping[str, str] | None = None) -> OfficialRegistry | None:
    raw = (env if env is not None else os.environ).get(REGISTRY_ENV, "").strip()
    if not raw:
        return None
    paths = [item for item in raw.split(os.pathsep) if item.strip()]
    return OfficialRegistry.from_paths(paths)


# ------------------------------------------------------------------ resolution
@dataclass(frozen=True, slots=True)
class MemberResolution:
    canonical_member_id: str
    canonical_name: str
    resolution: str              # OFFICIAL_ID / SEAT_AND_NAME / UNRESOLVED / AMBIGUOUS
    basis: str
    chamber: str
    official_ids: dict[str, str] = field(default_factory=dict)
    source_names: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()

    @property
    def confident(self) -> bool:
        return self.resolution in ("OFFICIAL_ID", "SEAT_AND_NAME")

    def to_dict(self) -> dict[str, Any]:
        return {"canonical_member_id": self.canonical_member_id, "canonical_name": self.canonical_name,
                "resolution": self.resolution, "basis": self.basis, "official_ids": dict(self.official_ids),
                "aliases": list(self.source_names), "notes": list(self.notes), "identity_version": IDENTITY_VERSION}


def _source_only(identity: SourceIdentity, resolution: str, basis: str, notes: tuple[str, ...] = ()) -> MemberResolution:
    return MemberResolution(f"SOURCE:{identity.key}", identity.name.display or identity.source_name, resolution, basis,
                            identity.chamber, source_names=(identity.source_name,), notes=notes)


class MemberResolver:
    def __init__(self, registry: OfficialRegistry | None = None) -> None:
        self.registry = registry

    def resolve(self, identities: Iterable[SourceIdentity]) -> dict[str, MemberResolution]:
        """Resolve a batch (every source identity in view); keyed by ``SourceIdentity.key``."""

        pending: dict[str, SourceIdentity] = {}
        for identity in identities:
            pending.setdefault(identity.key, identity)
        out: dict[str, MemberResolution] = {}
        official: dict[str, list[SourceIdentity]] = defaultdict(list)
        members: dict[str, RegistryMember] = {}
        leftovers: list[SourceIdentity] = []
        for identity in pending.values():
            if not identity.name.family:
                out[identity.key] = _source_only(identity, "UNRESOLVED", "SOURCE_NAME_INCOMPLETE")
                continue
            found = self.registry.candidates(identity) if self.registry is not None else []
            if len(found) == 1:
                official[found[0].bioguide].append(identity)
                members[found[0].bioguide] = found[0]
            elif len(found) > 1:
                out[identity.key] = _source_only(identity, "AMBIGUOUS", "REGISTRY_MULTIPLE_CANDIDATES",
                                                 tuple(sorted(f"CANDIDATE:{item.bioguide}" for item in found)))
            else:
                leftovers.append(identity)
        for bioguide, group in official.items():
            member = members[bioguide]
            names = tuple(sorted({item.source_name for item in group}))
            chambers = {item.chamber for item in group}
            basis = "REGISTRY_SEAT_TERM_AND_SURNAME" if chambers == {"HOUSE"} else "REGISTRY_TERM_AND_NAME"
            for identity in group:
                out[identity.key] = MemberResolution(f"BIOGUIDE:{bioguide}", member.official_name, "OFFICIAL_ID", basis,
                                                     identity.chamber, {"bioguide": bioguide}, names)
        self._seat_groups([item for item in leftovers if item.chamber == "HOUSE" and item.seat], out)
        for identity in leftovers:
            if identity.key not in out:
                out[identity.key] = _source_only(identity, "UNRESOLVED", "NO_OFFICIAL_OR_SEAT_EVIDENCE")
        return out

    @staticmethod
    def _seat_groups(identities: list[SourceIdentity], out: dict[str, MemberResolution]) -> None:
        groups: dict[tuple[str, str, str, str], list[SourceIdentity]] = defaultdict(list)
        for identity in identities:
            if identity.name.given:
                groups[(identity.seat or "", identity.name.family, identity.name.given, identity.name.suffix)].append(identity)
        suffix_variants: dict[tuple[str, str, str], set[str]] = defaultdict(set)
        for seat, family, given, suffix in groups:
            suffix_variants[(seat, family, given)].add(suffix)
        for (seat, family, given, suffix), group in groups.items():
            notes: list[str] = []
            if len(suffix_variants[(seat, family, given)]) > 1:
                notes.append("SUFFIX_VARIANT_IN_SAME_SEAT_UNVERIFIED")
            initials = {item.name.middle_initials[:1] for item in group if item.name.middle_initials}
            if len(initials) > 1:
                for identity in group:
                    out[identity.key] = _source_only(identity, "AMBIGUOUS", "CONFLICTING_MIDDLE_INITIALS_IN_SEAT",
                                                     tuple(notes))
                continue
            display = sorted((item.name.display for item in group), key=lambda text: (-len(text.split()), text))[0]
            names = tuple(sorted({item.source_name for item in group}))
            canonical = f"HOUSE-SEAT:{seat}:{family.upper()}:{given.upper()}" + (f":{suffix.upper()}" if suffix else "")
            for identity in group:
                out[identity.key] = MemberResolution(canonical, display, "SEAT_AND_NAME",
                                                     "SAME_HOUSE_SEAT_SAME_GIVEN_SURNAME_SUFFIX", "HOUSE",
                                                     source_names=names, notes=tuple(notes))


__all__ = [
    "IDENTITY_VERSION", "MemberResolution", "MemberResolver", "NameParts", "OfficialRegistry", "REGISTRY_ENV",
    "RegistryMember", "SourceIdentity", "house_identity", "registry_from_env", "split_full_name", "split_name",
]
