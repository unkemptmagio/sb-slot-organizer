# AGENTS.md

User-facing pregame tool (companion to skyrim-to-stellar-blade, repo `sb-skyrim-anims`). One file: `slots.py` (lib + CLI), test `python tests/slots_test.py`.
- Never modify third-party pak files. Never commit game files or `slot_cache.json`.
- Keep README/CHANGELOG/docs/next.md current. Style: terse, `# ponytail:` marks shortcuts.
- Observability is required (see D:\Projects\AGENTS.md): a persistent log users can attach, host/version logged at startup, no silent waits, an 'If something goes wrong' section in the README. Keep that table row current.
