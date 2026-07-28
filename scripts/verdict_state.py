#!/usr/bin/env python3
"""Read a verdict on stdin and print the value of its ``verdict`` field.

Exit 0 and print the verdict word when the input carries exactly one JSON object with a
string ``verdict``. Anything else -- no JSON, several objects, a non-object, a missing or
non-string ``verdict`` -- prints nothing and exits 1. Callers read a pass from the printed
word, so unreadable input can only ever be a refusal.

Why this exists. `scripts/validate-goal.sh` and `scripts/hooks/pre-merge-gate.sh` both used
to decide a verdict with ``grep -qE '"verdict": *"pass"'`` over the whole output. That finds
the substring, not the field, and the two differ in the cases that matter:

- a blocking verdict whose findings quote the goal's own text, when the goal is about this
  very control and so contains verdict JSON;
- a prose preamble in front of the object, or a second object after it, where the pass
  belongs to something other than the verdict being read;
- output that is not JSON at all, which grep reports as "no pass" for the right reason and
  as "pass" the moment the word appears anywhere in it.

#32 replaced the grep in the goal checker after measuring the divergence. #38 brings the two
scripts that guard merges to the same reading, through one implementation rather than three
-- `scripts/goal-body-hash.sh` is the precedent, and the reason is the same: copies drift,
and a drifted verdict reader is a control that lies in whichever direction it drifted.

A fenced block is tolerated because the two inputs differ in shape. The validator's raw
model output is meant to be a bare object; the comment the merge gate reads is that object
wrapped in a ```json fence under a marker line, because that is what
`scripts/validate-goal.sh` posts. The first fenced block wins when there is one, and the
whole input is tried when there is not.
"""

from __future__ import annotations

import json
import sys


def first_fenced_block(text: str) -> str | None:
    """Return the contents of the first ``` fenced block, or None if there is none."""
    lines = text.splitlines()
    opened: int | None = None
    for index, line in enumerate(lines):
        if line.strip().startswith("```"):
            if opened is None:
                opened = index
            else:
                return "\n".join(lines[opened + 1 : index])
    return None


def verdict_state(text: str) -> str | None:
    """The ``verdict`` field of the single JSON object in ``text``, or None."""
    block = first_fenced_block(text)
    candidate = block if block is not None else text
    try:
        # json.loads rejects trailing content, so two objects in a row are unreadable
        # rather than silently the first one. That is the intent: a second object means
        # the caller does not know which verdict it is holding.
        parsed = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(parsed, dict):
        return None
    state = parsed.get("verdict")
    return state if isinstance(state, str) else None


def main() -> int:
    state = verdict_state(sys.stdin.read())
    if state is None:
        return 1
    print(state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
