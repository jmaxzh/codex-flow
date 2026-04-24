# Repository Guidelines

## Project Structure & Module Organization
- `scripts/codex_automation_loops.py` is the CLI entrypoint for running native preset workflows.
- `scripts/_codex_orchestrator/` contains orchestration logic (runtime, prompting, output processing, paths, and workflow registry in `native_workflows/`).
- `tests/` stores automated tests; domain cases are split across `codex_orchestrator_cases_*.py` and re-exported via `tests/test_codex_orchestrator.py`.
- `presets/prompts/shared/` holds reusable role/prompt templates used by presets.
- `docs/specs/` is the source of truth for behavior contracts and migration notes.
- Runtime artifacts are written to `.codex-loop-state/` (run logs, summaries, state snapshots).

## Build, Test, and Development Commands
- Install dependencies: `python3.13 -m pip install --break-system-packages --user -r requirements.txt`
- Run a workflow preset: `python3 scripts/codex_automation_loops.py --preset implement_loop`
- Run all tests: `python3 -m pytest -q`
- Lint and format: `ruff check scripts tests` and `ruff format scripts tests`
- Type check: `basedpyright --warnings scripts tests`
- Install/verify hooks: `./scripts/setup_hooks.sh` (installs pre-commit and pre-push gates and runs both once).

## Coding Style & Naming Conventions
- Target runtime is Python 3.13.
- Use 4-space indentation, LF endings, and double quotes (`ruff format` enforces these).
- Keep lines at or under 130 characters.
- Follow strict typing expectations (`basedpyright` in strict mode).
- Naming: modules/functions/variables in `snake_case`, classes in `PascalCase`, constants in `UPPER_SNAKE_CASE`.
- Keep `scripts/` modules focused and small to satisfy repository size/quality gates.

## Testing Guidelines
- Test stack: `pytest` with `unittest.TestCase`-based case classes.
- Add new behavior coverage in `tests/codex_orchestrator_cases_<area>.py`.
- Name test methods as `test_<behavior>`.
- Run focused checks during development, for example: `python3 -m pytest -q -k presets_cli`.
- Ensure lint, type-check, and both hook stages pass before pushing.

## Commit & Pull Request Guidelines
- Follow Conventional Commit style seen in history (for example `feat: ...`, `fix: ...`; Chinese or English summaries are both used).
- Keep commit messages imperative and scoped to one logical change.
- PRs should include: purpose, key changes, impacted presets/specs, and verification commands run.
- Link related issues/spec docs and include CLI output snippets when behavior changes are user-visible.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read `specs/001-openspec-workflow-rename/plan.md`.
<!-- SPECKIT END -->
