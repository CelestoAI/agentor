# docs/

User-facing documentation lives at **https://docs.celesto.ai/agentor**, sourced
from the `mintlify-docs` repository. Nothing in this directory is published.

This used to hold an mkdocs site that deployed to `celestoai.github.io/agentor`
on every push to `main`. GitHub Pages was never enabled for the repository, so
that URL returned 404 for the site's whole life while the workflow reported
success. It also predated the v0.1.0 engine: its API reference covered eleven
modules and not one of `agentor/engine/`. Removed in favour of the one place
readers actually land.

## What is left here

- `dev/MIGRATION_PLAN.md` — the decision record for replacing the OpenAI Agents
  SDK with `agentor/engine/`. Kept because it explains why the engine looks the
  way it does, including the options rejected and what was measured.

Contributor-facing notes belong in [`AGENTS.md`](../AGENTS.md).
