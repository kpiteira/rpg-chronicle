"""Role names are spelled the same way everywhere they are written down.

Three places list the roles by hand: `agents/<role-id>.md`, the role-label list
in `docs/GOALS.md`, and the specialist dropdown in the issue form. A drift
between them is not cosmetic. `.github/workflows/goal-lifecycle.yml` derives the
roles from the labels actually in use and allows one active goal per distinct
label, so two spellings of one role read as two roles, each with its own active
goal -- the precise thing that check exists to prevent. This drifted once
already, between `agent:tpm` and `agent:technical-program-manager`.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Neither the validator nor the checker is a long-lived role with a goal queue. They are
# briefs for a headless process that reads one artifact and emits a verdict, so neither
# has a label, an issue-form option, or an active goal to be counted.
NOT_A_ROLE = {"goal-validator", "goal-checker"}


def role_ids() -> set[str]:
    return {path.stem for path in (ROOT / "agents").glob("*.md")} - NOT_A_ROLE


def labelled_roles() -> set[str]:
    text = (ROOT / "docs/GOALS.md").read_text()
    return set(re.findall(r"`agent:([a-z-]+)`", text))


def issue_form_roles() -> set[str]:
    text = (ROOT / ".github/ISSUE_TEMPLATE/specialist-goal.yml").read_text()
    options = re.search(r"options:\n((?:\s+- \S+\n)+)", text)
    assert options, "the specialist dropdown has no options"
    return set(re.findall(r"- (\S+)", options.group(1)))


def test_every_role_has_a_label() -> None:
    assert role_ids() - labelled_roles() == set()


def test_every_label_names_a_role() -> None:
    assert labelled_roles() - role_ids() == set()


def test_the_issue_form_offers_exactly_the_roles() -> None:
    assert issue_form_roles() == role_ids()
