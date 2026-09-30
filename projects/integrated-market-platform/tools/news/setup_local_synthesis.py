"""One-time, explicit setup of zero-cost local AI synthesis for Screener news.

Installs two pinned, hash-verified artifacts into the user-level IMP cache (never Git):

* llama.cpp ``llama-server`` (MIT, official ggml-org release, Windows Vulkan build — it
  uses an integrated GPU when present and falls back to CPU);
* ``Qwen/Qwen3-4B-GGUF`` Q4_K_M weights (Apache-2.0, official Qwen release) via the
  normal Hugging Face cache.

It then writes ``<IMP cache>/models/local-llm.json``. The API starts the server only
when an operator requests a synthesis, bound to 127.0.0.1, and stops it when idle.

    python tools/news/setup_local_synthesis.py           # download (once) + verify + manifest
    python tools/news/setup_local_synthesis.py --check   # offline verification only

Requires ``huggingface_hub`` (installed with ``transformers``) for the weights download.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from market_platform_foundation.intelligence.inference.local_provider import MANIFEST_RELATIVE  # noqa: E402
from market_platform_foundation.local_state.external_cache import imp_cache_dir, write_json_atomic  # noqa: E402

RUNTIME_VERSION = "b11269"
RUNTIME_ASSET = f"llama-{RUNTIME_VERSION}-bin-win-vulkan-x64.zip"
RUNTIME_URL = f"https://github.com/ggml-org/llama.cpp/releases/download/{RUNTIME_VERSION}/{RUNTIME_ASSET}"
RUNTIME_SHA256 = "34a27c239727047adc5aed80b656b13373ff136b27d28bd898a14b7b7283695a"
MODEL_REPO = "Qwen/Qwen3-4B-GGUF"
MODEL_REVISION = "bc640142c66e1fdd12af0bd68f40445458f3869b"
MODEL_FILE = "Qwen3-4B-Q4_K_M.gguf"
MODEL_SHA256 = "7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5"
MODEL_ID = "Qwen/Qwen3-4B-GGUF:Q4_K_M"
LICENSES = {"runtime": "MIT (ggml-org/llama.cpp)", "model": "Apache-2.0 (Qwen/Qwen3-4B-GGUF LICENSE)"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _runtime(root: Path, offline: bool) -> Path:
    target = root / "runtimes" / "llama.cpp" / f"{RUNTIME_VERSION}-win-vulkan-x64"
    server = target / "llama-server.exe"
    archive = root / "downloads" / RUNTIME_ASSET
    if not server.is_file():
        if offline:
            raise SystemExit("LOCAL_RUNTIME_NOT_INSTALLED")
        if not archive.is_file() or _sha256(archive) != RUNTIME_SHA256:
            archive.parent.mkdir(parents=True, exist_ok=True)
            request = urllib.request.Request(RUNTIME_URL, headers={"User-Agent": "integrated-market-platform-setup/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, archive.open("wb") as handle:
                for block in iter(lambda: response.read(1 << 20), b""):
                    handle.write(block)
        if _sha256(archive) != RUNTIME_SHA256:
            archive.unlink(missing_ok=True)
            raise SystemExit("LOCAL_RUNTIME_HASH_MISMATCH")
        with zipfile.ZipFile(archive) as bundle:
            for member in bundle.namelist():
                if not (target / member).resolve().is_relative_to(target.resolve()):
                    raise SystemExit("LOCAL_RUNTIME_ARCHIVE_UNSAFE_PATH")
            bundle.extractall(target)
        if not server.is_file():
            nested = next(target.rglob("llama-server.exe"), None)
            if nested is None:
                raise SystemExit("LOCAL_RUNTIME_SERVER_MISSING")
            server = nested
    return server


def _model(offline: bool) -> Path:
    from huggingface_hub import hf_hub_download  # type: ignore[import-not-found]

    path = Path(hf_hub_download(MODEL_REPO, MODEL_FILE, revision=MODEL_REVISION, local_files_only=offline))
    if _sha256(path) != MODEL_SHA256:
        raise SystemExit("LOCAL_MODEL_HASH_MISMATCH")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="verify installed artifacts offline; never download")
    args = parser.parse_args(argv)
    if platform.system() != "Windows":
        print("UNSUPPORTED_PLATFORM: this setup pins the Windows llama.cpp build; set IMP_LOCAL_LLM_BASE_URL and "
              "IMP_LOCAL_LLM_MODEL to a loopback OpenAI-compatible server instead")
        return 2
    root = imp_cache_dir()
    try:
        server = _runtime(root, offline=args.check)
        model = _model(offline=args.check)
    except ImportError:
        print("HUGGINGFACE_HUB_NOT_INSTALLED: install transformers (which provides huggingface_hub) first")
        return 2
    manifest = {"schema_version": "imp-local-model/1.0.0", "capability": "LOCAL_AI_SYNTHESIS",
                "runtime": "llama.cpp llama-server", "runtime_version": RUNTIME_VERSION, "runtime_path": str(server),
                "runtime_sha256_archive": RUNTIME_SHA256, "model_id": MODEL_ID, "revision": MODEL_REVISION,
                "model_path": str(model), "model_sha256": MODEL_SHA256, "model_bytes": model.stat().st_size,
                "context": 8192, "gpu_layers": 99, "licenses": LICENSES, "cost_usd": 0,
                "verified_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")}
    destination = root / MANIFEST_RELATIVE
    write_json_atomic(destination, manifest)
    print(json.dumps({"state": "READY", "runtime": str(server), "model_id": MODEL_ID, "revision": MODEL_REVISION,
                      "model_bytes": manifest["model_bytes"], "manifest": str(destination)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
