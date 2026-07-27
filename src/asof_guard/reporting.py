"""Dependency-free text, JSON, JUnit XML, and SARIF reporters."""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List
from urllib.parse import quote

from .models import FindingCategory, Verdict, format_timestamp
from .rules import RULES


SUPPORTED_FORMATS = ("text", "json", "junit", "sarif")


def render_text(verdict: Verdict) -> str:
    """Render a human-readable verdict with explicit assurance boundaries."""

    lines = [
        f"AsOfGuard verdict: {verdict.status.value.upper()}",
        f"Trace: {verdict.trace_id}",
        "Observable trace integrity: "
        + ("FAILED" if verdict.observable_failures else "NO OBSERVABLE FAILURE FOUND"),
        "Model-weight purity: UNVERIFIABLE (trace evidence cannot prove weight-level temporal purity)",
        f"Earliest invalid timestamp: {format_timestamp(verdict.earliest_invalid_timestamp) or '-'}",
    ]
    if verdict.contaminating_items:
        lines.append("Contaminating items:")
        for item_type, item_id in verdict.contaminating_items:
            lines.append(f"  - {item_type}:{item_id}")
    else:
        lines.append("Contaminating items: none observed")

    lines.append(
        "Findings: "
        f"{len(verdict.observable_failures)} observable failure(s), "
        f"{len(verdict.metadata_gaps)} metadata gap(s), "
        f"{len(verdict.uncertainties)} model-weight uncertainty item(s)"
    )
    for finding in verdict.findings:
        timestamp = format_timestamp(finding.timestamp)
        suffix = f" @ {timestamp}" if timestamp else ""
        lines.append(
            f"  [{finding.severity.value.upper()}] {finding.code} "
            f"({finding.category.value}) {finding.item_type}:{finding.item_id}{suffix}"
        )
        lines.append(f"    {finding.message}")
    return "\n".join(lines) + "\n"


def render_json(verdict: Verdict) -> str:
    """Render stable, pretty-printed JSON."""

    return json.dumps(verdict.to_dict(), indent=2, sort_keys=True) + "\n"


def render_junit(verdict: Verdict) -> str:
    """Render one JUnit test case per finding.

    Observable failures become ``failure`` nodes, missing metadata becomes
    ``error``, and model-weight uncertainty becomes ``skipped`` so CI systems do
    not accidentally conflate unverifiability with a demonstrated event failure.
    """

    test_count = max(1, len(verdict.findings))
    suite = ET.Element(
        "testsuite",
        {
            "name": "AsOfGuard",
            "tests": str(test_count),
            "failures": str(len(verdict.observable_failures)),
            "errors": str(len(verdict.metadata_gaps)),
            "skipped": str(len(verdict.uncertainties)),
        },
    )
    properties = ET.SubElement(suite, "properties")
    ET.SubElement(properties, "property", {"name": "trace_id", "value": verdict.trace_id})
    ET.SubElement(properties, "property", {"name": "verdict", "value": verdict.status.value})
    ET.SubElement(
        properties,
        "property",
        {"name": "model_weight_purity", "value": verdict.model_weight_purity},
    )
    if not verdict.findings:
        ET.SubElement(suite, "testcase", {"classname": "asof_guard", "name": "temporal_integrity"})
    else:
        for finding in verdict.findings:
            case = ET.SubElement(
                suite,
                "testcase",
                {
                    "classname": f"asof_guard.{finding.category.value}",
                    "name": f"{finding.code}:{finding.item_type}:{finding.item_id}",
                },
            )
            attrs = {"type": finding.code, "message": finding.message}
            body = json.dumps(finding.to_dict(), indent=2, sort_keys=True)
            if finding.category is FindingCategory.OBSERVABLE_FAILURE:
                ET.SubElement(case, "failure", attrs).text = body
            elif finding.category is FindingCategory.METADATA_GAP:
                ET.SubElement(case, "error", attrs).text = body
            else:
                ET.SubElement(case, "skipped", attrs).text = body
    ET.indent(suite, space="  ")
    return ET.tostring(suite, encoding="unicode", xml_declaration=True) + "\n"


def render_sarif(verdict: Verdict) -> str:
    """Render SARIF 2.1.0 suitable for code-scanning ingestion."""

    used_codes = sorted({finding.code for finding in verdict.findings})
    rules = [
        {
            "id": code,
            "name": code.lower(),
            "shortDescription": {"text": RULES[code]["title"]},
            "fullDescription": {"text": RULES[code]["description"]},
            "help": {"text": RULES[code]["remediation"]},
        }
        for code in used_codes
    ]
    results: List[Dict[str, Any]] = []
    for finding in verdict.findings:
        if finding.category is FindingCategory.OBSERVABLE_FAILURE:
            level = "error"
        elif finding.category is FindingCategory.METADATA_GAP:
            level = "warning"
        else:
            level = "note"
        uri = (
            "asofguard://trace/"
            + quote(verdict.trace_id, safe="")
            + "/"
            + quote(finding.item_type, safe="")
            + "/"
            + quote(finding.item_id, safe="")
        )
        result: Dict[str, Any] = {
            "ruleId": finding.code,
            "level": level,
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": uri},
                    }
                }
            ],
            "properties": {
                "category": finding.category.value,
                "itemType": finding.item_type,
                "itemId": finding.item_id,
                "timestamp": format_timestamp(finding.timestamp),
            },
        }
        if finding.evidence:
            result["properties"]["evidence"] = finding.evidence
        results.append(result)

    payload = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "AsOfGuard",
                        "semanticVersion": "0.1.0",
                        "rules": rules,
                    }
                },
                "results": results,
                "properties": {
                    "traceId": verdict.trace_id,
                    "verdict": verdict.status.value,
                    "modelWeightPurity": verdict.model_weight_purity,
                    "earliestInvalidTimestamp": format_timestamp(verdict.earliest_invalid_timestamp),
                },
            }
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_verdict(verdict: Verdict, output_format: str = "text") -> str:
    """Render a verdict using a supported output format."""

    renderers = {
        "text": render_text,
        "json": render_json,
        "junit": render_junit,
        "sarif": render_sarif,
    }
    try:
        renderer = renderers[output_format]
    except KeyError as exc:
        raise ValueError(f"unsupported output format: {output_format}") from exc
    return renderer(verdict)
