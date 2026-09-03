from collections.abc import Iterable, Iterator
from pathlib import Path

from squeeze_core.contracts import Observation

from .canonical_json import deserialize_observation, serialize_observation


def parse_jsonl(lines: Iterable[bytes | str]) -> Iterator[Observation]:
    for line_number, line in enumerate(lines, start=1):
        content = line.strip()
        if not content:
            continue
        try:
            yield deserialize_observation(content)
        except Exception as error:
            raise ValueError(f"invalid observation at JSONL line {line_number}: {error}") from error


def load_jsonl(path: Path) -> list[Observation]:
    with path.open("rb") as source:
        return list(parse_jsonl(source))


def serialize_jsonl(observations: Iterable[Observation]) -> bytes:
    return b"".join(serialize_observation(observation) + b"\n" for observation in observations)

