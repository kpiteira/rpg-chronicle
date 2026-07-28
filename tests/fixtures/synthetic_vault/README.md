---
type: index
category: fixture_notice
status: active
---

# README

This directory is an **invented** Obsidian vault. Nobody plays this campaign; no person,
place, faction or phrase in it was taken from anyone's notes. It was authored from the
vault-neutral characterisation in `docs/VAULT_INTEGRATION.md` — the shapes were copied,
the content never was.

It is here because `src/rpg_chronicle/vault/` needs something to read in CI, and because
the structural claims in that document are worth being checkable rather than believed.
`tests/test_vault_survey.py` walks this vault and asserts the shapes; run the same walk
by hand with:

```bash
uv run rpg-chronicle vault-survey tests/fixtures/synthetic_vault
```

The oddities are deliberate. A key spelled two ways, a link pointing at a note that was
never written, a note with nothing in it, a session whose frontmatter carries fields no
other session has — every one of those reproduces something a real vault does, and a
fixture that tidied them up would let software pass here and fail on contact with a
vault somebody actually keeps.

This note is part of the fixture and is counted by the survey like any other.
