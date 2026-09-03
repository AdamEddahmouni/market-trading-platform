"""Document hashing and exhibit retrieval policy. Do not fetch everything."""

from __future__ import annotations

from enum import StrEnum

from ..canonical import sha256_bytes


class DocumentRetrievalPolicy(StrEnum):
    METADATA_ONLY = "METADATA_ONLY"
    PRIMARY_DOCUMENT = "PRIMARY_DOCUMENT"
    HIGH_VALUE = "HIGH_VALUE"
    STRUCTURED_FACTS = "STRUCTURED_FACTS"


HIGH_VALUE_EXHIBITS = {"EX-99.1", "EX-99.2", "EX-10.1", "EX-1.1", "EX-4.1"}
LOW_VALUE_EXHIBITS = {"GRAPHIC", "ZIP", "JPG", "PNG", "GIF"}


def hash_document(payload: bytes) -> str:
    return sha256_bytes(payload)


def select_exhibits(
    *,
    form_type: str,
    exhibits: tuple[str, ...],
    policy: DocumentRetrievalPolicy,
) -> tuple[str, ...]:
    if policy == DocumentRetrievalPolicy.METADATA_ONLY:
        return ()
    selected: list[str] = []
    for exhibit in exhibits:
        token = exhibit.upper()
        if token in LOW_VALUE_EXHIBITS:
            continue
        if policy == DocumentRetrievalPolicy.HIGH_VALUE:
            if token in HIGH_VALUE_EXHIBITS or token.startswith("EX-99") or token.startswith("EX-10"):
                selected.append(exhibit)
            elif form_type.upper().startswith("424") or form_type.upper() in {"S-1", "S-3"}:
                if "PROSPECTUS" in token or token.startswith("EX-"):
                    selected.append(exhibit)
        elif policy == DocumentRetrievalPolicy.PRIMARY_DOCUMENT:
            continue
        else:
            selected.append(exhibit)
    return tuple(selected)
