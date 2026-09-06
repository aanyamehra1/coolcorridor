"""Shared validation helpers and typed result/error objects."""

from __future__ import annotations

from dataclasses import dataclass, field


class DataQualityError(Exception):
    """Raised when input data is missing or too degraded to proceed safely."""


@dataclass
class QualityReport:
    """Accumulates non-fatal warnings surfaced to the user in the UI."""

    warnings: list[str] = field(default_factory=list)

    def add(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0


def require_columns(df, columns: list[str], context: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise DataQualityError(
            f"{context}: missing required column(s) {missing}. "
            f"Available columns: {list(df.columns)}"
        )
