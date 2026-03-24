"""Version parsing and comparison for PZ build versions."""

from __future__ import annotations

from dataclasses import dataclass
from functools import total_ordering


@total_ordering
@dataclass(frozen=True)
class PZVersion:
    """A parsed PZ version string (e.g., '42.3.1')."""

    major: int
    minor: int
    patch: int
    raw: str

    @classmethod
    def parse(cls, version_str: str) -> PZVersion:
        """Parse a version string like '42.3.1' or '42.0.0'.

        Handles partial versions: '42' -> 42.0.0, '42.3' -> 42.3.0
        """
        version_str = version_str.strip()
        parts = version_str.split(".")

        major = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
        minor = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        patch = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0

        return cls(major=major, minor=minor, patch=patch, raw=version_str)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PZVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, PZVersion):
            return NotImplemented
        return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)

    def __hash__(self) -> int:
        return hash((self.major, self.minor, self.patch))

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"


def version_in_range(
    version: PZVersion,
    min_version: str | None = None,
    max_version: str | None = None,
) -> bool:
    """Check if a version falls within a min/max range (inclusive)."""
    if min_version:
        if version < PZVersion.parse(min_version):
            return False
    if max_version:
        if version > PZVersion.parse(max_version):
            return False
    return True
