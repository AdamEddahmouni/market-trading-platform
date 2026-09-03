from pathlib import Path

from squeeze_core.contracts import Observation
from squeeze_core.serialization import load_jsonl


def load_fixture(path: str | Path) -> list[Observation]:
    return load_jsonl(Path(path))

