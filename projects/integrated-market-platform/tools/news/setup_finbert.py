"""One-time, explicit FinBERT setup for Screener news sentiment.

Downloads the pinned ``ProsusAI/finbert`` revision into the normal Hugging Face
cache, verifies the weight file's SHA-256 against the value pinned here, and
writes ``<IMP cache>/models/finbert.json``. Normal Screener operation then loads
the model with ``local_files_only=True`` and never downloads.

    python tools/news/setup_finbert.py            # download (once) + verify + manifest
    python tools/news/setup_finbert.py --check    # offline verification only

Requires the optional ``torch`` (CPU) and ``transformers`` packages in the
backend interpreter; they are not part of the foundation dependency lock.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.local_state.external_cache import imp_cache_dir, write_json_atomic  # noqa: E402
from market_platform_foundation.news.finbert_sentiment import MANIFEST_RELATIVE  # noqa: E402

MODEL_ID = "ProsusAI/finbert"
REVISION = "4556d13015211d73dccd3fdd39d39232506f3e43"
FILES = ("config.json", "pytorch_model.bin", "special_tokens_map.json", "tokenizer_config.json", "vocab.txt")
WEIGHTS_SHA256 = "e15a7b5738df7f17553399b6d94c6e2ff69c89245d066e8e5d183f5803a554e3"
LICENSE_NOTE = ("Publisher ProsusAI distributes FinBERT from its Apache-2.0 GitHub repository (ProsusAI/finBERT), "
                "which names this Hugging Face repository as the model's release location; the Hub card itself "
                "declares no license. Fine-tuned on Financial PhraseBank (Malo et al. 2014, CC BY-NC-SA 3.0): "
                "suitable for this private, non-commercial workstation; commercial redistribution needs review.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(offline: bool) -> Path:
    from huggingface_hub import snapshot_download  # type: ignore[import-not-found]

    return Path(snapshot_download(MODEL_ID, revision=REVISION, allow_patterns=list(FILES), local_files_only=offline))


def _verify(path: Path) -> dict[str, object]:
    missing = [name for name in FILES if not (path / name).is_file()]
    if missing:
        raise SystemExit(f"FINBERT_FILES_MISSING: {', '.join(missing)}")
    weights = _sha256(path / "pytorch_model.bin")
    if weights != WEIGHTS_SHA256:
        raise SystemExit("FINBERT_WEIGHTS_HASH_MISMATCH")
    labels = {str(value).lower() for value in json.loads((path / "config.json").read_text(encoding="utf-8"))["id2label"].values()}
    if labels != {"positive", "neutral", "negative"}:
        raise SystemExit("FINBERT_UNEXPECTED_LABELS")
    return {"files": {name: {"bytes": (path / name).stat().st_size,
                             "sha256": weights if name == "pytorch_model.bin" else _sha256(path / name)} for name in FILES},
            "bytes": sum((path / name).stat().st_size for name in FILES)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify the cached model offline; never download")
    args = parser.parse_args(argv)
    try:
        path = _snapshot(offline=args.check)
    except ImportError:
        print("TRANSFORMERS_NOT_INSTALLED: install CPU torch and transformers into the backend interpreter first")
        return 2
    except Exception as exc:  # noqa: BLE001 — setup reports a stable code, never a traceback
        print(f"FINBERT_NOT_CACHED: {type(exc).__name__}")
        return 2
    verified = _verify(path)
    manifest = {"schema_version": "imp-local-model/1.0.0", "capability": "FINBERT_SENTIMENT", "model_id": MODEL_ID,
                "revision": REVISION, "path": str(path), "license_note": LICENSE_NOTE,
                "verified_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), **verified}
    destination = imp_cache_dir() / MANIFEST_RELATIVE
    write_json_atomic(destination, manifest)
    print(json.dumps({"state": "READY", "model_id": MODEL_ID, "revision": REVISION, "bytes": verified["bytes"],
                      "manifest": str(destination)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
