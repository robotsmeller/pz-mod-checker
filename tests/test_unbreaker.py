"""Tests for Unbreaker coverage classification."""

from pz_mod_checker.unbreaker import classify, coverage_lookup


COVERAGE = {
    "version": "0.8.0",
    "redirects": [
        {"module": "ISUI/ISContextMenu", "category": "vanilla_global", "verified": True},
        {"module": "Json", "category": "unrecoverable", "verified": False},
        {"module": "AquaConfig", "category": "filename_mismatch", "verified": False},
        "not a dict",
    ],
}


def test_classify():
    lookup = coverage_lookup(COVERAGE)
    assert classify("ISUI/ISContextMenu", lookup) == "fixed"
    assert classify("Json", lookup) == "unrecoverable"
    # staged but unverified is not a promise Unbreaker fixes it
    assert classify("AquaConfig", lookup) == "unknown"
    assert classify("MyMod/Internal", lookup) == "unknown"
