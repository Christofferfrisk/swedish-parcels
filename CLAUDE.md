# swedish-parcels

Home Assistant integration that parses shipping notification emails to track parcels.

## Architecture

- Parser-first: each carrier/sender is a module under `src/swedish_parcels/parsers/`.
- Each parser is independently testable against `.eml` fixtures.
- The HA integration scaffold comes last and wraps the pure-Python parsing core.

## Conventions

- Python 3.13, `uv` for deps, `ruff` for lint/format, `pytest` for tests.
- Async only where it has to touch Home Assistant; pure parsing stays sync.
- Fixtures in `fixtures/<carrier>/` are gitignored (they contain personal data).
- Every parser must have at least 3 fixture-based tests before being merged.
- Use `email.policy.default` when parsing — never the legacy `email` API.
- Type hints required; `mypy --strict` must pass.

## Code style

- **Minimal comments.** No module-level prose docstrings, no section-divider
  comments, no comments that restate what the code does. Only add a comment
  when the *why* is non-obvious and a reader would otherwise be confused.
- One-line docstrings only when they add information the signature doesn't.
- Tests don't need docstrings — the test name should be the description.

## Git

- Commit at logical milestones with conventional commit messages.
- Never commit anything under `fixtures/` or any `.eml` file.
- Never commit `.env`.

## Out of scope (for now)

- Live carrier API polling (email-only).
- OAuth flows (IMAP password auth only in v0.1).
- Custom Lovelace card (separate repo, later).
