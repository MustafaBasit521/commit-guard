"""SARIF 2.1.0 output, for CI / GitHub code scanning.

``git-security-tool scan --all --format sarif`` prints this to stdout; upload
it with the ``github/codeql-action/upload-sarif`` step to populate the
repository's Security tab.
"""

import json

from git_security.models.finding import Finding, Severity

_INFO_URI = "https://github.com/MustafaBasit521/commit-guard"

_LEVEL = {
    Severity.INFO: "note",
    Severity.LOW: "note",
    Severity.MEDIUM: "warning",
    Severity.HIGH: "error",
    Severity.CRITICAL: "error",
}


def to_sarif(findings: list[Finding]) -> str:
    rules: dict[str, dict] = {}
    results: list[dict] = []

    for finding in findings:
        rule_id = f"{finding.tool}.{finding.rule}"
        rules.setdefault(
            rule_id,
            {
                "id": rule_id,
                "name": finding.rule or finding.tool,
                "shortDescription": {"text": finding.rule or finding.tool},
            },
        )
        results.append(
            {
                "ruleId": rule_id,
                "level": _LEVEL.get(finding.severity, "warning"),
                "message": {"text": finding.message},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": finding.file},
                            "region": {"startLine": max(finding.line, 1)},
                        }
                    }
                ],
            }
        )

    doc = {
        "version": "2.1.0",
        "$schema": (
            "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/"
            "Schemata/sarif-schema-2.1.0.json"
        ),
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "git-security-tool",
                        "informationUri": _INFO_URI,
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }
    return json.dumps(doc, indent=2)
