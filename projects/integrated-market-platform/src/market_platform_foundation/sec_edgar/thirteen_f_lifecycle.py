"""Managed lifecycle for the local 13F index (Screener S14).

S12 built the 13F index by hand from SEC Form 13F data-set ZIPs. This module owns the
whole lifecycle around that same index (``thirteen_f_index.build_index`` /
``ThirteenFIndex``), outside the repository:

    discover the SEC's published data sets → compare with the active generation
    → download missing ones → verify → rebuild a candidate from a deterministic
    source set → validate + smoke-query the candidate → atomically switch the
    ``CURRENT`` pointer → keep the previous generation for rollback.

Storage (any OS; no drive letters)::

    <root>/sources/<name>_form13f.zip        verified SEC data sets
    <root>/sources/<name>_form13f.zip.json   sidecar: url, sha256, bytes, downloaded_at
    <root>/generations/<id>/index.sqlite     one immutable index generation
    <root>/generations/<id>/manifest.json    its provenance manifest
    <root>/generations/<id>.building/        a candidate (never read by the Screener)
    <root>/CURRENT                           {"generation": <id>, "manifest_sha256": ...}
    <root>/refresh.lock                      one refresh at a time
    <root>/last_check.json, last_refresh.json

A candidate is always a **full deterministic rebuild** from the chosen source set: the
S12 build is ~48 s for two data sets, and a rebuild can never inherit a half-applied
increment. The pointer file is replaced with ``os.replace`` (atomic on POSIX and
Windows), so a reader sees either the old or the new generation, never a mix. Any
failure before the swap leaves the active generation untouched.

13F is publication-driven. A refresh makes the index current *for the data sets the SEC
has published*; it never makes quarter-end holdings live. Nothing here is on the
Screener request path: the Screener reads ``status()`` (files only, no network).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import sqlite3
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from .thirteen_f_index import SCHEMA, SourceIntegrityError, ThirteenFIndex, build_index, verify_archive

TOOL_VERSION = "sec_edgar.thirteen_f_lifecycle/1.0.0"
MANIFEST_SCHEMA = "imp-13f-generation-manifest/1"
LISTING_URL = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"
SEC_ORIGIN = "https://www.sec.gov"
DEFAULT_DATASETS = 2          # current + prior filing window: the quarter-over-quarter comparison S12 uses
KEEP_GENERATIONS = 3          # active + parent + one more; older ones are pruned best-effort
LOCK_STALE_S = 6 * 3600.0     # a lock older than this is from a dead refresh (builds take about a minute)
CHECK_STALE_DAYS = 7
MAX_DATASET_BYTES = 2 * 1024 ** 3

_MONTHS = {name: index for index, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), start=1)}
# Current naming (filing-date window): 01jun2026-31aug2026_form13f.zip; legacy quarterly: 2023q4_form13f.zip.
_WINDOW = re.compile(r"^(\d{2})([a-z]{3})(\d{4})-(\d{2})([a-z]{3})(\d{4})_form13f\.zip$")
_QUARTER = re.compile(r"^(\d{4})q([1-4])_form13f\.zip$")
_HREF = re.compile(r"""href\s*=\s*["']([^"']+_form13f\.zip)["']""", re.I)


class RefreshError(RuntimeError):
    """A refresh stopped before publishing; ``code`` is stable, ``stage`` names where."""

    def __init__(self, code: str, stage: str) -> None:
        super().__init__(code)
        self.code = code
        self.stage = stage


# ------------------------------------------------------------------ discovery
@dataclass(frozen=True, slots=True)
class DatasetRef:
    """One published SEC Form 13F data set; coverage is the filing-date window its name states."""

    name: str
    url: str
    coverage_start: str
    coverage_end: str


def _window_date(day: str, month: str, year: str) -> date | None:
    try:
        return date(int(year), _MONTHS[month], int(day))
    except (KeyError, ValueError):
        return None


def dataset_from_name(name: str, url: str) -> DatasetRef | None:
    """Coverage from the official file name; an unrecognised name is skipped, never guessed."""

    lower = name.lower()
    window = _WINDOW.match(lower)
    if window:
        start, end = _window_date(*window.group(1, 2, 3)), _window_date(*window.group(4, 5, 6))
        if start is None or end is None or end < start:
            return None
        return DatasetRef(lower, url, start.isoformat(), end.isoformat())
    quarter = _QUARTER.match(lower)
    if quarter:
        year, number = int(quarter.group(1)), int(quarter.group(2))
        start = date(year, 3 * number - 2, 1)
        end = (date(year + 1, 1, 1) if number == 4 else date(year, 3 * number + 1, 1)) - timedelta(days=1)
        return DatasetRef(lower, url, start.isoformat(), end.isoformat())
    return None


def parse_listing(html: str, *, base_url: str = SEC_ORIGIN) -> list[DatasetRef]:
    """Data sets linked from the SEC's Form 13F data-sets page, oldest window first.

    The SEC publishes the list as that HTML page (no machine-readable index is offered);
    only links to ``*_form13f.zip`` whose names carry a parseable window are admitted.
    """

    found: dict[str, DatasetRef] = {}
    for href in _HREF.findall(html or ""):
        url = urljoin(base_url + "/", href.strip())
        ref = dataset_from_name(url.rsplit("/", 1)[-1], url)
        if ref is not None and url.startswith(SEC_ORIGIN + "/"):
            found.setdefault(ref.name, ref)
    return sorted(found.values(), key=lambda ref: (ref.coverage_end, ref.name))


# ------------------------------------------------------------------ default live transport (operator runs only)
def _user_agent(env: Callable[[str], str | None]) -> str:
    from .transport import require_user_agent

    return require_user_agent(env("SEC_USER_AGENT") or "")


def default_fetch_listing(env: Callable[[str], str | None] = os.environ.get) -> str:
    from .transport import SecTransport

    return SecTransport(user_agent=_user_agent(env)).get(LISTING_URL).decode("utf-8", "replace")


def default_download(url: str, dest: Path, env: Callable[[str], str | None] = os.environ.get) -> None:
    """Stream one data set to ``dest`` with the SEC Fair Access User-Agent; size-checked."""

    from urllib.request import Request, urlopen

    from .transport import SecTransport

    agent = _user_agent(env)
    SecTransport(user_agent=agent)._throttle()  # share the process-wide SEC request budget
    request = Request(url, headers={"User-Agent": agent})
    written = 0
    with urlopen(request, timeout=120) as response, dest.open("wb") as handle:
        expected = response.headers.get("Content-Length")
        while chunk := response.read(1 << 20):
            written += len(chunk)
            if written > MAX_DATASET_BYTES:
                raise SourceIntegrityError("THIRTEEN_F_SOURCE_TOO_LARGE")
            handle.write(chunk)
    if expected is not None and expected.isdigit() and int(expected) != written:
        raise SourceIntegrityError("THIRTEEN_F_SOURCE_TRUNCATED")


# ------------------------------------------------------------------ helpers
def _now_iso(clock: Callable[[], float]) -> str:
    return datetime.fromtimestamp(clock(), tz=UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for attempt in range(20):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            # Windows refuses to replace a file another process has open (a reader of CURRENT for a
            # moment); the old file stays intact, so waiting briefly and retrying is safe.
            if attempt == 19:
                raise
            time.sleep(0.05)


# ------------------------------------------------------------------ store
class ThirteenFStore:
    """One external 13F data root. All mutation happens under ``refresh.lock``."""

    def __init__(self, root: str | Path, *, clock: Callable[[], float] = time.time) -> None:
        self.root = Path(root)
        self.clock = clock

    # paths
    @property
    def sources(self) -> Path:
        return self.root / "sources"

    @property
    def generations(self) -> Path:
        return self.root / "generations"

    @property
    def pointer(self) -> Path:
        return self.root / "CURRENT"

    @property
    def lock_path(self) -> Path:
        return self.root / "refresh.lock"

    def source_path(self, name: str) -> Path:
        return self.sources / name

    # -------------------------------------------------------------- active generation
    def current_generation(self) -> str | None:
        pointer = _read_json(self.pointer)
        generation = pointer.get("generation") if pointer else None
        return generation if isinstance(generation, str) and generation else None

    def generation_dir(self, generation: str) -> Path:
        return self.generations / generation

    def manifest(self, generation: str) -> dict[str, Any] | None:
        return _read_json(self.generation_dir(generation) / "manifest.json")

    def current_index_path(self) -> Path | None:
        """The active index file, or None when no valid generation is published."""

        generation = self.current_generation()
        if generation is None:
            return None
        path = self.generation_dir(generation) / "index.sqlite"
        return path if path.is_file() else None

    def verify_generation(self, generation: str, *, deep: bool = False) -> str | None:
        """None when the generation is intact, else a stable problem code."""

        manifest = self.manifest(generation)
        index = self.generation_dir(generation) / "index.sqlite"
        if manifest is None:
            return "MANIFEST_MISSING"
        if manifest.get("schema_version") != MANIFEST_SCHEMA or manifest.get("generation") != generation:
            return "MANIFEST_INVALID"
        if not index.is_file():
            return "INDEX_MISSING"
        if index.stat().st_size != manifest.get("index_bytes"):
            return "INDEX_SIZE_MISMATCH"
        if deep and sha256_file(index) != manifest.get("index_sha256"):
            return "INDEX_HASH_MISMATCH"
        return None

    # -------------------------------------------------------------- lock
    def lock_info(self) -> dict[str, Any] | None:
        """The lock's payload; a lock still being written (empty or partial) is dated by its mtime."""

        info = _read_json(self.lock_path)
        if info is None:
            try:
                info = {"started_at_epoch": self.lock_path.stat().st_mtime}
            except FileNotFoundError:
                return None
        return info

    def lock_active(self) -> bool:
        # Liveness is wall-clock time (lock payloads and mtimes are wall-clock), never the injected clock.
        info = self.lock_info()
        if info is None:
            return False
        try:
            started = float(info.get("started_at_epoch") or 0.0)
        except (TypeError, ValueError):
            started = 0.0
        return time.time() - started < LOCK_STALE_S

    def acquire(self, *, break_stale: bool = True) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"pid": os.getpid(), "host": socket.gethostname(), "started_at": _now_iso(self.clock),
                              "started_at_epoch": time.time(), "tool": TOOL_VERSION}).encode("utf-8")
        for _ in range(2):
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                if break_stale and not self.lock_active() and self.lock_path.exists():
                    # A dead refresh left this behind (older than LOCK_STALE_S): age is the only portable
                    # liveness signal (os.kill(pid, 0) terminates processes on Windows).
                    self.lock_path.unlink(missing_ok=True)
                    continue
                raise RefreshError("REFRESH_ALREADY_RUNNING", "lock") from None
            with os.fdopen(fd, "wb") as handle:
                handle.write(payload)
            return
        raise RefreshError("REFRESH_ALREADY_RUNNING", "lock")

    def release(self) -> None:
        self.lock_path.unlink(missing_ok=True)

    # -------------------------------------------------------------- crash leftovers
    def clean_leftovers(self) -> list[str]:
        """Remove partial downloads and unfinished candidates (call under the lock)."""

        removed: list[str] = []
        if self.sources.is_dir():
            for item in self.sources.glob("*.part"):
                item.unlink(missing_ok=True)
                removed.append(f"sources/{item.name}")
        if self.generations.is_dir():
            for item in self.generations.glob("*.building"):
                shutil.rmtree(item, ignore_errors=True)
                removed.append(f"generations/{item.name}")
        for name in ("CURRENT.tmp",):
            if (self.root / name).exists():
                (self.root / name).unlink(missing_ok=True)
                removed.append(name)
        return removed

    # -------------------------------------------------------------- sources
    def local_sources(self) -> dict[str, dict[str, Any]]:
        """Verified data sets on disk: name → sidecar."""

        out: dict[str, dict[str, Any]] = {}
        if not self.sources.is_dir():
            return out
        for sidecar in sorted(self.sources.glob("*_form13f.zip.json")):
            info = _read_json(sidecar)
            name = sidecar.name[: -len(".json")]
            if info and (self.sources / name).is_file():
                out[name] = info
        return out

    def ensure_source(self, ref: DatasetRef, download: Callable[[str, Path], None]) -> dict[str, Any]:
        """Return the verified sidecar for ``ref``, downloading it when absent.

        An existing file whose hash no longer matches its sidecar is quarantined and the
        refresh fails closed (``THIRTEEN_F_SOURCE_HASH_MISMATCH``); the next refresh downloads it again.
        """

        self.sources.mkdir(parents=True, exist_ok=True)
        path, sidecar_path = self.source_path(ref.name), self.source_path(ref.name + ".json")
        sidecar = _read_json(sidecar_path)
        if path.is_file() and sidecar is not None:
            if sha256_file(path) != sidecar.get("sha256") or path.stat().st_size != sidecar.get("bytes"):
                os.replace(path, path.with_name(path.name + ".quarantine"))
                sidecar_path.unlink(missing_ok=True)
                raise RefreshError("THIRTEEN_F_SOURCE_HASH_MISMATCH", "verify")
            return sidecar
        part = path.with_name(path.name + ".part")
        part.unlink(missing_ok=True)
        try:
            download(ref.url, part)
            verify_archive(part)
        except SourceIntegrityError as exc:
            part.unlink(missing_ok=True)
            raise RefreshError(str(exc).split(":")[0], "download") from exc
        except OSError as exc:
            part.unlink(missing_ok=True)
            raise RefreshError("THIRTEEN_F_SOURCE_DOWNLOAD_FAILED", "download") from exc
        info = {"name": ref.name, "url": ref.url, "sha256": sha256_file(part), "bytes": part.stat().st_size,
                "coverage_start": ref.coverage_start, "coverage_end": ref.coverage_end,
                "downloaded_at": _now_iso(self.clock)}
        os.replace(part, path)
        _write_json_atomic(sidecar_path, info)
        return info

    def import_source(self, zip_path: Path) -> dict[str, Any]:
        """Admit an operator-downloaded official data set (same verification as a download)."""

        ref = dataset_from_name(zip_path.name, f"{SEC_ORIGIN}/files/structureddata/data/form-13f-data-sets/{zip_path.name.lower()}")
        if ref is None:
            raise RefreshError("THIRTEEN_F_SOURCE_NAME_UNRECOGNISED", "import")
        return self.ensure_source(ref, lambda _url, dest: shutil.copyfile(zip_path, dest))

    # -------------------------------------------------------------- pointer
    def publish(self, generation: str, *, previous: str | None) -> None:
        manifest_sha = sha256_file(self.generation_dir(generation) / "manifest.json")
        _write_json_atomic(self.pointer, {"generation": generation, "manifest_sha256": manifest_sha,
                                          "previous": previous, "published_at": _now_iso(self.clock)})

    def prune(self) -> list[str]:
        """Drop old generations beyond ``KEEP_GENERATIONS`` (never the active one or its parent)."""

        if not self.generations.is_dir():
            return []
        current = self.current_generation()
        keep = {current, (self.manifest(current) or {}).get("parent_generation") if current else None}
        published = sorted((item for item in self.generations.iterdir() if item.is_dir() and not item.name.endswith(".building")),
                           key=lambda item: item.name, reverse=True)
        removed = []
        for item in published[KEEP_GENERATIONS:]:
            if item.name in keep:
                continue
            shutil.rmtree(item, ignore_errors=True)  # an index still open on Windows is kept until next time
            if not item.exists():
                removed.append(item.name)
        return removed


# ------------------------------------------------------------------ validation
def default_smoke(index_path: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    """Open the candidate like the Screener does and query its most-held CUSIP after the newest window."""

    # closing(): sqlite3's own context manager only commits; an open handle blocks the publish rename on Windows.
    with closing(sqlite3.connect(index_path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise RefreshError("INDEX_QUICK_CHECK_FAILED", "validate")
        top = db.execute("SELECT cusip FROM positions GROUP BY cusip ORDER BY COUNT(*) DESC LIMIT 1").fetchone()
    if top is None:
        raise RefreshError("INDEX_HAS_NO_POSITIONS", "validate")
    index = ThirteenFIndex.load(index_path)
    try:
        if index.meta.get("generation") != manifest["generation"]:
            raise RefreshError("INDEX_GENERATION_MISMATCH", "validate")
        moment = datetime.combine(date.fromisoformat(manifest["coverage_end"]) + timedelta(days=2),
                                  datetime.min.time(), tzinfo=UTC)
        section = index.section([top[0]], now=moment)
    finally:
        index.close()
    if section["state"] not in ("CURRENT_AS_FILED", "PARTIAL") or not section.get("holder_count"):
        raise RefreshError("INDEX_SMOKE_QUERY_FAILED", "validate")
    return {"cusip": top[0], "period": section["period"], "holder_count": section["holder_count"], "state": section["state"]}


# ------------------------------------------------------------------ lifecycle
Hook = Callable[[str], None]


class ThirteenFLifecycle:
    """Operator/background workflow over one ``ThirteenFStore``; every network call is injectable."""

    def __init__(self, store: ThirteenFStore, *, fetch_listing: Callable[[], str] | None = None,
                 download: Callable[[str, Path], None] | None = None, datasets: int = DEFAULT_DATASETS,
                 builder: Callable[..., dict[str, Any]] = build_index,
                 smoke: Callable[[Path, dict[str, Any]], dict[str, Any]] = default_smoke,
                 hook: Hook | None = None) -> None:
        if datasets < 1:
            raise ValueError("DATASETS_MUST_BE_POSITIVE")
        self.store = store
        self._fetch_listing = fetch_listing or default_fetch_listing
        self._download = download or default_download
        self.datasets = datasets
        self._builder = builder
        self._smoke = smoke
        self._hook = hook or (lambda _stage: None)   # test seam: raise here to simulate a crash at a stage

    # -------------------------------------------------------------- check
    def discover(self) -> list[DatasetRef]:
        try:
            listing = self._fetch_listing()
        except (OSError, ValueError) as exc:
            code = str(exc) if str(exc).isupper() or str(exc).startswith("SEC_") else "SEC_LISTING_UNAVAILABLE"
            raise RefreshError(code, "discover") from exc
        refs = parse_listing(listing)
        if not refs:
            raise RefreshError("SEC_LISTING_HAS_NO_DATASETS", "discover")
        return refs

    def wanted(self, refs: list[DatasetRef]) -> list[DatasetRef]:
        return refs[-self.datasets:]

    def check(self) -> dict[str, Any]:
        """Compare the SEC's published data sets with the active generation; records ``last_check.json``."""

        checked_at = _now_iso(self.store.clock)
        self.store.root.mkdir(parents=True, exist_ok=True)
        try:
            refs = self.discover()
        except RefreshError as exc:
            result = {"checked_at": checked_at, "ok": False, "error": exc.code}
            _write_json_atomic(self.store.root / "last_check.json", result)
            return result
        wanted = self.wanted(refs)
        current = self.store.current_generation()
        indexed = {item["name"] for item in (self.store.manifest(current) or {}).get("source_datasets", [])} if current else set()
        missing = [ref.name for ref in wanted if ref.name not in indexed]
        result = {"checked_at": checked_at, "ok": True, "available": [asdict(ref) for ref in refs],
                  "newest_available": refs[-1].name, "newest_available_coverage_end": refs[-1].coverage_end,
                  "wanted": [ref.name for ref in wanted], "missing": missing, "active_generation": current,
                  "is_current_for_available_datasets": bool(current) and not missing}
        _write_json_atomic(self.store.root / "last_check.json", result)
        return result

    # -------------------------------------------------------------- refresh
    def refresh(self, *, dry_run: bool = False, force: bool = False, break_stale_lock: bool = True) -> dict[str, Any]:
        """Bring the index up to the newest published data sets; the active one survives any failure."""

        store = self.store
        try:
            store.acquire(break_stale=break_stale_lock)
        except RefreshError as exc:
            # Another refresh owns the store: report it and leave its lock and files alone.
            return {"outcome": "FAILED", "error": exc.code, "stage": exc.stage, "dry_run": dry_run,
                    "generation": store.current_generation()}
        started = time.monotonic()
        stage = "prepare"
        result: dict[str, Any] = {"started_at": _now_iso(store.clock), "dry_run": dry_run}
        try:
            result["cleaned"] = store.clean_leftovers()
            stage = "discover"
            check = self.check()
            if not check["ok"]:
                raise RefreshError(check["error"], "discover")
            wanted = [DatasetRef(**item) for item in check["available"] if item["name"] in check["wanted"]]
            result["wanted"] = [ref.name for ref in wanted]
            previous = store.current_generation()
            previous_invalid = previous is not None and store.verify_generation(previous) is not None
            if not check["missing"] and not force and not previous_invalid:
                result.update({"outcome": "NO_CHANGE", "generation": previous})
                return result
            if dry_run:
                result.update({"outcome": "WOULD_REFRESH", "missing": check["missing"], "generation": previous})
                return result
            stage = "download"
            sources = []
            for ref in wanted:
                self._hook("download")
                sources.append(store.ensure_source(ref, self._download))
            timings: dict[str, float] = {}
            stage = "build"
            generation, candidate, manifest = self._build_candidate(sources, previous, timings)
            stage = "validate"
            self._hook("validate")
            mark = time.monotonic()
            manifest["smoke"] = self._smoke(candidate / "index.sqlite", manifest)
            timings["validate_s"] = round(time.monotonic() - mark, 3)
            manifest["timings"] = timings
            _write_json_atomic(candidate / "manifest.json", manifest)
            stage = "publish"
            self._hook("before_swap")
            final = store.generation_dir(generation)
            os.replace(candidate, final)
            self._hook("after_candidate")
            mark = time.monotonic()
            store.publish(generation, previous=previous)
            timings["swap_s"] = round(time.monotonic() - mark, 4)
            stage = "prune"
            result["pruned"] = store.prune()
            result.update({"outcome": "PUBLISHED", "generation": generation, "previous": previous,
                           "manifest": manifest, "timings": timings})
            return result
        except RefreshError as exc:
            result.update({"outcome": "FAILED", "error": exc.code, "stage": exc.stage,
                           "generation": store.current_generation()})
            return result
        except SourceIntegrityError as exc:
            result.update({"outcome": "FAILED", "error": str(exc).split(":")[0], "stage": stage,
                           "generation": store.current_generation()})
            return result
        except Exception as exc:  # noqa: BLE001 - any other failure must leave the active index as it was
            result.update({"outcome": "FAILED", "error": f"UNEXPECTED_{type(exc).__name__.upper()}", "stage": stage,
                           "generation": store.current_generation()})
            return result
        finally:
            store.clean_leftovers()
            result["finished_at"] = _now_iso(store.clock)
            result["wall_s"] = round(time.monotonic() - started, 3)
            summary = {key: result.get(key) for key in ("started_at", "finished_at", "outcome", "error", "stage",
                                                           "generation", "wall_s", "dry_run")}
            _write_json_atomic(store.root / "last_refresh.json", summary)
            store.release()

    def _build_candidate(self, sources: list[dict[str, Any]], previous: str | None,
                         timings: dict[str, float]) -> tuple[str, Path, dict[str, Any]]:
        store = self.store
        ordered = sorted(sources, key=lambda item: (item["coverage_end"], item["name"]))
        source_key = hashlib.sha256("|".join(f"{item['name']}:{item['sha256']}" for item in ordered).encode()).hexdigest()
        stamp = datetime.fromtimestamp(store.clock(), tz=UTC).strftime("%Y%m%dT%H%M%SZ")
        generation = f"gen-{stamp}-{source_key[:10]}"
        if store.generation_dir(generation).exists():
            generation = f"{generation}-{os.getpid()}"
        candidate = store.generations / f"{generation}.building"
        candidate.mkdir(parents=True)
        coverage_start = min(item["coverage_start"] for item in ordered)
        coverage_end = max(item["coverage_end"] for item in ordered)
        meta = {"generation": generation, "coverage_start": coverage_start, "coverage_end": coverage_end,
                "tool_version": TOOL_VERSION, "source_sha256": source_key}
        self._hook("build")
        mark = time.monotonic()
        stats = self._builder([store.source_path(item["name"]) for item in ordered], candidate / "index.sqlite", meta=meta)
        timings["build_s"] = round(time.monotonic() - mark, 3)
        if not stats.get("holdings_reports") or not stats.get("positions"):
            raise RefreshError("INDEX_EMPTY", "build")
        index = candidate / "index.sqlite"
        manifest = {
            "schema_version": MANIFEST_SCHEMA, "generation": generation, "generated_at": _now_iso(store.clock),
            "index_schema": SCHEMA, "tool_version": TOOL_VERSION, "parent_generation": previous,
            "source_datasets": [{key: item[key] for key in ("name", "url", "sha256", "bytes", "coverage_start",
                                                            "coverage_end", "downloaded_at")} for item in ordered],
            "source_sha256": source_key, "coverage_start": coverage_start, "coverage_end": coverage_end,
            "filing_date_min": stats.get("filing_date_min"), "filing_date_max": stats.get("filing_date_max"),
            "filing_count": stats["holdings_reports"], "submission_count": stats["submissions"],
            "position_count": stats["positions"], "line_count": stats["lines"],
            "duplicate_accessions": stats.get("duplicate_accessions", 0),
            "index_bytes": index.stat().st_size, "index_sha256": sha256_file(index)}
        _write_json_atomic(candidate / "manifest.json", manifest)
        return generation, candidate, manifest

    # -------------------------------------------------------------- rollback
    def rollback(self) -> dict[str, Any]:
        """Re-point ``CURRENT`` at the active generation's parent, if it is intact."""

        store = self.store
        store.acquire()
        try:
            current = store.current_generation()
            parent = (store.manifest(current) or {}).get("parent_generation") if current else None
            if not parent:
                return {"outcome": "FAILED", "error": "NO_PARENT_GENERATION", "generation": current}
            problem = store.verify_generation(parent, deep=True)
            if problem is not None:
                return {"outcome": "FAILED", "error": f"PARENT_{problem}", "generation": current}
            store.publish(parent, previous=current)
            return {"outcome": "ROLLED_BACK", "generation": parent, "previous": current}
        finally:
            store.release()


# ------------------------------------------------------------------ status (no network; Screener-safe)
def status(root: str | Path | None, *, clock: Callable[[], float] = time.time) -> dict[str, Any]:
    """Freshness and refresh state of the local index, read from files only.

    ``refresh_state``: NOT_CONFIGURED · INDEX_INVALID · REFRESHING · REFRESH_AVAILABLE ·
    CURRENT_AS_FILED (the index holds the newest data sets the SEC has published, as of the
    last check) · UNCHECKED · SOURCE_ERROR (the last check could not reach the SEC listing;
    the index itself is still served). None of these says anything is live.
    """

    if not root:
        return {"refresh_state": "NOT_CONFIGURED", "refresh_reason": "IMP_13F_DATA_ROOT_NOT_SET", "managed": False}
    store = ThirteenFStore(root, clock=clock)
    now = datetime.fromtimestamp(clock(), tz=UTC)
    out: dict[str, Any] = {"managed": True, "refreshing": store.lock_active()}
    check = _read_json(store.root / "last_check.json")
    last_refresh = _read_json(store.root / "last_refresh.json")
    if last_refresh and last_refresh.get("outcome") == "FAILED":
        out["last_refresh_error"] = {key: last_refresh.get(key) for key in ("error", "stage", "finished_at")}
    generation = store.current_generation()
    if generation is None:
        state, reason = ("REFRESHING", "FIRST_BUILD_RUNNING") if out["refreshing"] else ("NOT_CONFIGURED", "THIRTEEN_F_INDEX_NOT_BUILT")
        return {**out, "refresh_state": state, "refresh_reason": reason, "generation": None}
    problem = store.verify_generation(generation)
    manifest = store.manifest(generation) or {}
    datasets = manifest.get("source_datasets") or []
    generated = manifest.get("generated_at")
    age = None
    if generated:
        age = round((now - datetime.fromisoformat(generated.replace("Z", "+00:00"))).total_seconds() / 86400, 2)
    out.update({
        "generation": generation, "generated_at": generated, "age_days": age,
        "latest_indexed_dataset": datasets[-1]["name"] if datasets else None,
        "indexed_through": manifest.get("coverage_end"), "coverage_start": manifest.get("coverage_start"),
        "latest_source_filing_date": manifest.get("filing_date_max"), "source_dataset_count": len(datasets),
        "source_datasets": [item.get("name") for item in datasets], "filing_count": manifest.get("filing_count"),
        "position_count": manifest.get("position_count"), "index_sha256": manifest.get("index_sha256"),
        "checked_at": check.get("checked_at") if check else None,
        "newest_available": check.get("newest_available") if check and check.get("ok") else None,
        "is_current_for_available_datasets": None,
    })
    if problem is not None:
        return {**out, "refresh_state": "INDEX_INVALID", "refresh_reason": problem}
    if out["refreshing"]:
        return {**out, "refresh_state": "REFRESHING", "refresh_reason": "SERVING_PREVIOUS_GENERATION"}
    if check is None:
        return {**out, "refresh_state": "UNCHECKED", "refresh_reason": "NEVER_CHECKED"}
    if not check.get("ok"):
        return {**out, "refresh_state": "SOURCE_ERROR", "refresh_reason": check.get("error") or "CHECK_FAILED"}
    indexed = {item.get("name") for item in datasets}
    missing = [name for name in check.get("wanted", []) if name not in indexed]
    out["is_current_for_available_datasets"] = not missing
    out["missing_datasets"] = missing
    checked = datetime.fromisoformat(str(check["checked_at"]).replace("Z", "+00:00"))
    stale_check = now - checked > timedelta(days=CHECK_STALE_DAYS)
    if missing:
        return {**out, "refresh_state": "REFRESH_AVAILABLE", "refresh_reason": "NEWER_SEC_DATASET_PUBLISHED"}
    return {**out, "refresh_state": "CURRENT_AS_FILED",
            "refresh_reason": "LAST_CHECK_OLDER_THAN_7_DAYS" if stale_check else None}


def load_current_index(root: str | Path) -> tuple[ThirteenFIndex | None, str | None]:
    """Open the active generation read-only; (None, code) when there is none or it is invalid."""

    store = ThirteenFStore(root)
    generation = store.current_generation()
    if generation is None:
        return None, "THIRTEEN_F_INDEX_NOT_BUILT"
    problem = store.verify_generation(generation)
    if problem is not None:
        return None, problem
    try:
        return ThirteenFIndex.load(store.generation_dir(generation) / "index.sqlite"), None
    except (sqlite3.Error, ValueError):
        return None, "INDEX_UNREADABLE"


class ManagedIndex:
    """Screener-side view of a managed root: the active generation plus its freshness.

    Reads files only (no network); re-reads the ``CURRENT`` pointer at most every
    ``recheck_s`` and swaps to a newly published generation between requests. While a
    refresh runs, requests keep reading the previous generation (``REFRESHING``).
    """

    def __init__(self, root: str | Path, *, clock: Callable[[], float] = time.time, recheck_s: float = 30.0) -> None:
        self.root = Path(root)
        self._clock = clock
        self._recheck_s = recheck_s
        self._lock = threading.Lock()
        self._index: ThirteenFIndex | None = None
        self._generation: str | None = None
        self._problem: str | None = None
        self._status: dict[str, Any] = {}
        self._checked = float("-inf")

    def _refresh(self) -> tuple[ThirteenFIndex | None, dict[str, Any]]:
        with self._lock:
            now = self._clock()
            if now - self._checked < self._recheck_s:
                return self._index, self._status
            self._checked = now
            self._status = status(self.root, clock=self._clock)
            generation = ThirteenFStore(self.root).current_generation()
            if generation != self._generation or (self._index is None and generation is not None):
                index, problem = load_current_index(self.root)
                old, self._index, self._problem = self._index, index, problem
                self._generation = generation if index is not None else None
                if old is not None:
                    old.close()  # waits for an in-flight query on the old generation
            return self._index, self._status

    def status(self) -> dict[str, Any]:
        return dict(self._refresh()[1])

    def section(self, cusips: list[str], *, now: datetime) -> dict[str, Any]:
        for _ in range(2):
            index, freshness = self._refresh()
            if index is None:
                state = freshness.get("refresh_state")
                section_state = ("INDEX_INVALID" if state == "INDEX_INVALID" else "REFRESHING" if state == "REFRESHING"
                                 else "NOT_CONFIGURED")
                return {"state": section_state, "reason": freshness.get("refresh_reason") or self._problem,
                        "index": freshness}
            try:
                return {**index.section(cusips, now=now), "index": freshness}
            except sqlite3.ProgrammingError:
                self._checked = float("-inf")   # the generation was swapped mid-request: re-open and retry once
        return {"state": "INDEX_INVALID", "reason": "INDEX_SWAPPED_DURING_REQUEST", "index": self.status()}


def iter_generations(root: str | Path) -> Iterable[str]:
    store = ThirteenFStore(root)
    if not store.generations.is_dir():
        return []
    return sorted(item.name for item in store.generations.iterdir() if item.is_dir() and not item.name.endswith(".building"))


__all__ = [
    "DEFAULT_DATASETS", "DatasetRef", "LISTING_URL", "MANIFEST_SCHEMA", "ManagedIndex", "RefreshError", "TOOL_VERSION",
    "ThirteenFLifecycle", "ThirteenFStore", "dataset_from_name", "default_smoke", "iter_generations",
    "load_current_index", "parse_listing", "sha256_file", "status",
]
