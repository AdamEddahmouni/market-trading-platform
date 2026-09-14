"""Wave 1 harness fail-closed errors."""

from __future__ import annotations


class Wave1HarnessError(Exception):
    code: str

    def __init__(self, code: str, *, details: dict[str, object] | None = None) -> None:
        self.code = code
        self.details = dict(details or {})
        super().__init__(code)


class Wave1ExportGateError(Wave1HarnessError):
    pass


class Wave1ConfigError(Wave1HarnessError):
    pass
