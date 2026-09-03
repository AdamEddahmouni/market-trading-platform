from collections.abc import Iterable


def normalize_conditions(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(value.strip() for value in values if value.strip())

