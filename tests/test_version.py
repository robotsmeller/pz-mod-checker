"""Tests for version parsing and comparison."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.rules.version import PZVersion, version_in_range


def test_parse_full_version():
    v = PZVersion.parse("42.3.1")
    assert v.major == 42
    assert v.minor == 3
    assert v.patch == 1


def test_parse_partial_version():
    v = PZVersion.parse("42")
    assert v.major == 42
    assert v.minor == 0
    assert v.patch == 0


def test_parse_two_part():
    v = PZVersion.parse("42.3")
    assert v.major == 42
    assert v.minor == 3
    assert v.patch == 0


def test_version_comparison():
    v1 = PZVersion.parse("42.0.0")
    v2 = PZVersion.parse("42.1.0")
    v3 = PZVersion.parse("42.1.1")
    v4 = PZVersion.parse("41.78.16")

    assert v1 < v2
    assert v2 < v3
    assert v4 < v1
    assert v1 == PZVersion.parse("42.0.0")


def test_version_in_range():
    v = PZVersion.parse("42.3.0")
    assert version_in_range(v, "42.0.0", "42.5.0")
    assert version_in_range(v, "42.3.0", "42.3.0")
    assert not version_in_range(v, "42.4.0")
    assert not version_in_range(v, None, "42.2.0")


def test_version_str():
    v = PZVersion.parse("42.3.1")
    assert str(v) == "42.3.1"


if __name__ == "__main__":
    test_parse_full_version()
    test_parse_partial_version()
    test_parse_two_part()
    test_version_comparison()
    test_version_in_range()
    test_version_str()
    print("All version tests passed.")
