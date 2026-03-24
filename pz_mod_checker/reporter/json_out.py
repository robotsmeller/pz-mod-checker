"""JSON output for scan results."""

from __future__ import annotations

import json
from dataclasses import asdict

from ..rules.engine import Finding


def findings_to_json(results: dict[str, list[Finding]], pretty: bool = True) -> str:
    """Convert findings to a JSON string.

    Args:
        results: Findings keyed by mod_id.
        pretty: If True, format with indentation.

    Returns:
        JSON string.
    """
    output = {
        "total_mods_with_issues": len(results),
        "total_findings": sum(len(f) for f in results.values()),
        "summary": {
            "breaking": sum(1 for fs in results.values() for f in fs if f.severity == "breaking"),
            "warning": sum(1 for fs in results.values() for f in fs if f.severity == "warning"),
            "info": sum(1 for fs in results.values() for f in fs if f.severity == "info"),
        },
        "mods": {
            mod_id: [asdict(f) for f in findings]
            for mod_id, findings in sorted(results.items())
        },
    }

    indent = 2 if pretty else None
    return json.dumps(output, indent=indent, default=str)
