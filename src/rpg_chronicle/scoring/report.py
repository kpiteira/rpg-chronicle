"""Rendering a score report for a person to read.

The layout is chosen so a number cannot be lifted out of it alone. Every dimension prints
its basis and its caveat immediately underneath the value, and the contamination state
prints above all of them rather than in a footnote, because a reader who stops after the
first screen must have stopped somewhere honest.
"""

from __future__ import annotations

import json
from typing import Any

RULE = "-" * 78

#: The headline numbers worth putting on the first line of a dimension, in the order they
#: read best. Anything not listed still appears in the JSON report; this is a reading aid,
#: not a filter on what was computed.
HEADLINES = {
    "entity_capture": ("recall_by_name", "recall_anchor_corroborated"),
    "plot_capture": ("coverage_upper_bound", "term_overlap_share"),
    "unsupported_claims": (
        "negative_control_hits",
        "entities_absent_from_cited_turns",
        "claims_citing_missing_turns",
    ),
    "surfaced_errors": ("detected_errors", "surfaced", "unsurfaced"),
    "processing_time": ("wall_clock_s", "realtime_factor"),
    "peak_memory": ("peak_rss_mib",),
    "question_count": ("review_questions", "questions_per_recorded_hour"),
    "review_burden": ("estimated_seconds_per_recorded_hour", "within_target"),
}


def _wrap(text: str, indent: str = "    ", width: int = 78) -> str:
    words = text.split()
    lines: list[str] = []
    current = indent
    for word in words:
        if len(current) + len(word) + 1 > width and current.strip():
            lines.append(current.rstrip())
            current = indent
        current += word + " "
    if current.strip():
        lines.append(current.rstrip())
    return "\n".join(lines)


def render(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"score: {report['session_id']} against {report['manifest_id']}")
    lines.append(f"harness {report['harness_version']}, verdict: {report['verdict'].upper()}")
    lines.append(RULE)

    contamination = report["contamination"]
    lines.append(f"contamination: {contamination['state'].upper()}")
    lines.append(_wrap(contamination["explanation"]))
    if report["verdict"] == "withheld":
        lines.append(
            _wrap(
                "Every dimension that reads the answer key is withheld below: it was "
                "computed, and its value is not printed, because a number beside a "
                "warning is still a number somebody will quote. Time, memory, question "
                "count and review burden do not read the answer key, so they are "
                "unaffected and are reported normally."
            )
        )
    lines.append("")

    provenance = report["truth_provenance"]
    census = ", ".join(f"{key}={value}" for key, value in sorted(provenance["targets_by_basis"].items()))
    lines.append(f"truth provenance: annotation_status={provenance['annotation_status']}; {census or 'no targets'}")
    lines.append(_wrap(provenance["note"]))
    lines.append("")

    basis = report["time_basis"]
    lines.append(
        f"time basis: {basis['hypothesis']} (offset {basis['offset_ms']} ms); "
        f"{basis['anchors_inside_session']}/{basis['anchors_total']} anchors land inside "
        f"the session's turns"
    )
    lines.append(RULE)

    coverage = report["coverage"]
    lines.append(
        f"dimensions: {coverage['reported']} reported, "
        f"{coverage['withheld_as_contaminated']} withheld as contaminated, "
        f"{len(coverage['unmeasurable'])} unmeasurable, covering the "
        f"{coverage['criteria_named_by_m2']} criteria M2 names"
    )
    lines.append("")

    for dimension in report["dimensions"]:
        if not dimension["measured"]:
            lines.append(f"{dimension['name']} ({dimension['criterion']}): NOT MEASURED")
            lines.append(_wrap(f"missing: {dimension['missing']}"))
            lines.append("")
            continue
        if dimension.get("contaminated"):
            lines.append(f"{dimension['name']} ({dimension['criterion']}): WITHHELD")
            lines.append(_wrap(f"computed, and not reported: {dimension['withheld_because']}"))
            lines.append(_wrap(f"basis it would have had: {dimension['basis']}"))
            lines.append("")
            continue
        value = dimension["value"]
        headline = ", ".join(
            f"{key}={value[key]}" for key in HEADLINES.get(dimension["name"], ()) if key in value
        )
        lines.append(f"{dimension['name']} ({dimension['criterion']}): {headline or 'see report'}")
        lines.append(_wrap(f"basis: {dimension['basis']}"))
        lines.append(_wrap(f"does not mean: {dimension['caveat']}"))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_json(report: dict[str, Any]) -> str:
    return json.dumps(report, indent=2) + "\n"
