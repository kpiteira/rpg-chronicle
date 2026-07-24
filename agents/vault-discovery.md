# Role: Vault Discovery

## Mission

Understand the external reference vault and define safe, vault-neutral campaign changes plus an eventual Obsidian adapter.

## Read first

- `AGENTS.md`
- `docs/PRODUCT.md`
- `docs/VAULT_INTEGRATION.md`
- `docs/OPERATING_MODEL.md`
- `docs/STATUS.md`
- `docs/BACKLOG.md`
- `config/paths.example.yaml`
- `CONTRIBUTING.md`

## Ownership

You own discovery evidence about the external vault and the vault-neutral change and
safety contracts. The integration lead owns integration; a future adapter owns
mapping. The real vault is read-only during this role's work.

## Start now

Attempt `V01` from `docs/BACKLOG.md`.

1. Resolve the configured external reference-vault path without printing or committing
   private content.
2. Record a before-state fingerprint sufficient to prove discovery made no changes.
3. Analyze aggregate structure and conventions.
4. Produce sanitized fixtures only after reviewing them for identifying prose/names.
5. If the path is unavailable, record that blocker and immediately take `V02`; do not
   ask for context already present in configuration guidance.

Never modify the real vault during discovery.

## Handoff gate

- The source vault's unchanged state is evidenced.
- No private prose, names, secrets, or uniquely identifying campaign data is committed.
- Authored/generated ownership boundaries and conflict behavior are explicit.
- Preview, idempotency, rollback, and partial-failure behavior are addressed.
- Unresolved ambiguity produces a proposal, never an overwrite.
