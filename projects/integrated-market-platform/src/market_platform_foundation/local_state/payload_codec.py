"""Lossless compact storage for evidence payloads: zlib with a preset dictionary per scope.

A Moomoo L1 receipt is about 2.7 KB of JSON, mostly the same field names and ``"N/A"`` option fields in every
row. Plain per-row zlib saves 2x; a dictionary built from the store's own earlier rows of the same scope saves
about 10x (2026-10-27: 2,666 -> 248 bytes per row). The store grew 2.2 GB a day and would have reached its
approved budget within days.

* ``encode`` returns ``IMPZ1:<dictionary id>:`` + the compressed bytes as a BLOB, or the text unchanged when the
  scope has no dictionary yet. Every encoded value is decompressed and compared byte for byte before it is
  returned; any difference keeps the plain text. Nothing is ever stored that does not decode to the input.
* ``decode`` returns text rows unchanged and fails closed on an unknown dictionary or damaged bytes.
* Dictionaries are immutable rows of ``payload_dictionaries``, keyed by the first 16 hex digits of their SHA-256,
  created lazily (no schema version change: code that predates the codec ignores the table and still opens the
  store). A dictionary is built once per scope from that scope's latest stored plain rows.

Identity hashes (``record_id``, revisions) are computed over the uncompressed JSON by the writers, so the codec
never changes what a record is, only how many bytes it takes.
"""

from __future__ import annotations

import hashlib
import threading
import time
import zlib
from typing import Any, Iterable

MAGIC = b"IMPZ1:"
DICTIONARY_BYTES = 32 * 1024  # zlib's whole window
SAMPLE_ROWS = 64
MIN_SAMPLE_ROWS = 32
LEVEL = 6
TABLE_DDL = ("CREATE TABLE IF NOT EXISTS payload_dictionaries ("
             "dictionary_id TEXT PRIMARY KEY, scope TEXT NOT NULL, sha256 TEXT NOT NULL, "
             "created_ns INTEGER NOT NULL, dictionary BLOB NOT NULL)")
_ID_LENGTH = 16


class PayloadCodecError(ValueError):
    """A stored payload cannot be decoded; it is never guessed at."""


def is_encoded(value: Any) -> bool:
    return isinstance(value, (bytes, bytearray, memoryview)) and bytes(value[:len(MAGIC)]) == MAGIC


def build_dictionary(samples: Iterable[str]) -> bytes:
    """The tail of the concatenated samples: zlib prefers matches near the end of the dictionary."""
    return b"".join(sample.encode("utf-8") for sample in samples)[-DICTIONARY_BYTES:]


class _Primed:
    """A compressor and a decompressor with the dictionary already loaded; each use works on a copy.
    Loading a 32 KB dictionary costs more than compressing one 3 KB row, which matters for a back-fill."""

    def __init__(self, dictionary: bytes) -> None:
        self.dictionary = dictionary
        self.compressor = zlib.compressobj(LEVEL, zdict=dictionary)
        self.decompressor = zlib.decompressobj(zdict=dictionary)


def compress(text: str, dictionary_id: str, dictionary: bytes, primed: _Primed | None = None) -> bytes | None:
    """The encoded BLOB, or None when it is not smaller or does not decode back to ``text`` exactly."""
    raw = text.encode("utf-8")
    compressor = primed.compressor.copy() if primed is not None else zlib.compressobj(LEVEL, zdict=dictionary)
    blob = MAGIC + dictionary_id.encode("ascii") + b":" + compressor.compress(raw) + compressor.flush()
    if len(blob) >= len(raw):
        return None
    try:
        if decompress(blob, dictionary, primed) != text:
            return None
    except PayloadCodecError:
        return None
    return blob


def split(value: bytes) -> tuple[str, bytes]:
    head = len(MAGIC)
    dictionary_id = value[head:head + _ID_LENGTH]
    if len(dictionary_id) != _ID_LENGTH or value[head + _ID_LENGTH:head + _ID_LENGTH + 1] != b":":
        raise PayloadCodecError("PAYLOAD_CODEC_CORRUPT")
    return dictionary_id.decode("ascii"), value[head + _ID_LENGTH + 1:]


def decompress(value: bytes, dictionary: bytes, primed: _Primed | None = None) -> str:
    _, data = split(bytes(value))
    decompressor = primed.decompressor.copy() if primed is not None else zlib.decompressobj(zdict=dictionary)
    try:
        raw = decompressor.decompress(data) + decompressor.flush()
    except zlib.error as exc:
        raise PayloadCodecError("PAYLOAD_CODEC_CORRUPT") from exc
    if not decompressor.eof or decompressor.unused_data:
        raise PayloadCodecError("PAYLOAD_CODEC_CORRUPT")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PayloadCodecError("PAYLOAD_CODEC_CORRUPT") from exc


class PayloadCodec:
    """Dictionaries of one store, cached. ``connection`` is a LocalStateConnection (or anything with
    ``execute`` returning rows); every method that writes runs inside the caller's transaction."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self._by_id: dict[str, bytes] = {}
        self._by_scope: dict[str, tuple[str, bytes]] = {}
        self._primed: dict[str, _Primed] = {}
        self._lock = threading.Lock()
        self._table_ready = False

    def _primed_for(self, dictionary_id: str, dictionary: bytes) -> _Primed:
        with self._lock:
            primed = self._primed.get(dictionary_id)
            if primed is None:
                primed = self._primed[dictionary_id] = _Primed(dictionary)
            return primed

    def forget(self, scope: str) -> None:
        """Drop a cached scope, e.g. after the transaction that recorded its dictionary rolled back."""
        with self._lock:
            found = self._by_scope.pop(scope, None)
            if found is not None:
                self._by_id.pop(found[0], None)
                self._primed.pop(found[0], None)
            self._table_ready = False

    def ensure_table(self) -> None:
        if not self._table_ready:
            self.connection.execute(TABLE_DDL)
            self._table_ready = True

    def _table_exists(self) -> bool:
        if self._table_ready:
            return True
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='payload_dictionaries'").fetchone()
        self._table_ready = row is not None
        return self._table_ready

    def dictionary(self, dictionary_id: str) -> bytes:
        with self._lock:
            cached = self._by_id.get(dictionary_id)
        if cached is not None:
            return cached
        row = None
        if self._table_exists():
            row = self.connection.execute("SELECT sha256, dictionary FROM payload_dictionaries WHERE dictionary_id=?",
                                          (dictionary_id,)).fetchone()
        if row is None:
            raise PayloadCodecError(f"PAYLOAD_CODEC_UNKNOWN_DICTIONARY:{dictionary_id}")
        dictionary = bytes(row[1])
        if hashlib.sha256(dictionary).hexdigest() != row[0] or not row[0].startswith(dictionary_id):
            raise PayloadCodecError(f"PAYLOAD_CODEC_DICTIONARY_MISMATCH:{dictionary_id}")
        with self._lock:
            self._by_id[dictionary_id] = dictionary
        return dictionary

    def for_scope(self, scope: str) -> tuple[str, bytes] | None:
        with self._lock:
            cached = self._by_scope.get(scope)
        if cached is not None:
            return cached
        if not self._table_exists():
            return None
        row = self.connection.execute("SELECT dictionary_id FROM payload_dictionaries WHERE scope=? "
                                      "ORDER BY created_ns LIMIT 1", (scope,)).fetchone()
        if row is None:
            return None
        found = (str(row[0]), self.dictionary(str(row[0])))
        with self._lock:
            self._by_scope[scope] = found
        return found

    def create(self, scope: str, samples: list[str]) -> tuple[str, bytes] | None:
        """Record this scope's dictionary from ``samples``; the scope's first dictionary always wins."""
        existing = self.for_scope(scope)
        if existing is not None:
            return existing
        if len(samples) < MIN_SAMPLE_ROWS:
            return None
        dictionary = build_dictionary(samples)
        digest = hashlib.sha256(dictionary).hexdigest()
        self.ensure_table()
        self.connection.execute("INSERT OR IGNORE INTO payload_dictionaries VALUES (?,?,?,?,?)",
                                (digest[:_ID_LENGTH], scope, digest, time.time_ns(), dictionary))
        with self._lock:
            self._by_scope.pop(scope, None)
        return self.for_scope(scope)

    def encode(self, scope: str, text: str) -> str | bytes:
        found = self.for_scope(scope)
        if found is None:
            return text
        blob = compress(text, found[0], found[1], self._primed_for(*found))
        return text if blob is None else blob

    def decode(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        if not is_encoded(value):
            raise PayloadCodecError("PAYLOAD_CODEC_CORRUPT")
        dictionary_id, _ = split(bytes(value))
        dictionary = self.dictionary(dictionary_id)
        return decompress(bytes(value), dictionary, self._primed_for(dictionary_id, dictionary))


def stream_scope(provider: str, capability: str) -> str:
    return f"market_stream:{provider}:{capability}"
