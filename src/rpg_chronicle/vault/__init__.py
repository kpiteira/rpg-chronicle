"""Read-only understanding of an Obsidian-style vault.

Nothing in this package writes to a vault, and nothing in it is an adapter. It exists
to answer the question a campaign-change contract cannot be designed without: what does
the destination actually look like, and which parts of it belong to the person who wrote
it.

`survey` walks a vault and reports its shape. `boundary` decides whether a region of a
note is the tool's to touch. `digest` proves a vault was not modified without naming
anything inside it.
"""

from __future__ import annotations

from .boundary import (
    AMBIGUOUS,
    AUTHORED,
    RECLAIMED,
    TOOL_OWNED,
    GeneratedRegion,
    classify_region,
    section_body,
    unsafe_targets,
)
from .digest import VaultDigest, vault_digest
from .survey import (
    FrontmatterField,
    Link,
    LinkTopology,
    Note,
    Section,
    VaultSurvey,
    format_report,
    survey_vault,
)

__all__ = [
    "AMBIGUOUS",
    "AUTHORED",
    "RECLAIMED",
    "TOOL_OWNED",
    "FrontmatterField",
    "GeneratedRegion",
    "Link",
    "LinkTopology",
    "Note",
    "Section",
    "VaultDigest",
    "VaultSurvey",
    "classify_region",
    "format_report",
    "section_body",
    "survey_vault",
    "unsafe_targets",
    "vault_digest",
]
