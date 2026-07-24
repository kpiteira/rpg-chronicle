# Vault integration direction

Vault discovery begins in parallel with processing work. The existing vault lives outside the repository and is referenced through configuration or a local symlink.

## Discovery goals

- Identify existing note types and conventions
- Understand what worked well in the previous campaign
- Separate authored content from generated content
- Determine safe create, update, merge, and rollback behavior
- Build sanitized fixtures that preserve structure without private content

## Vault-neutral contract

The product should first produce a structured campaign-change package containing:

- Session record
- Scenes
- New entities
- Proposed entity updates
- Timeline events
- Relationship changes
- Quest changes
- Open questions
- Source evidence
- Confidence and review status

An Obsidian adapter maps that package into the chosen vault structure. Uncertainty should be resolved before vault application, not discovered inside the vault.
