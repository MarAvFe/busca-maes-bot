# Contributing to BuscaMaes

Thanks for helping! This doc covers local development workflows to keep the codebase maintainable.

## Setup

```bash
# Install uv (one time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Clone and set up
git clone git@github.com:MarAvFe/busca-maes-bot.git
cd busca-maes-bot
uv sync
```

## Common tasks

### Run tests
```bash
uv run pytest          # all tests
uv run pytest -v       # verbose
uv run pytest -k name  # filter by test name
uv run pytest --live   # include @pytest.mark.live (hits real TSE)
```

### Fix lint issues automatically
```bash
uv run ruff check --fix .   # auto-fix lint issues (import ordering, unused imports, etc.)
uv run ruff format .        # format code to style
```

### Check types
```bash
uv run mypy .
```

### Run all checks (lint + types + tests)
```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

## Before pushing

Run the full CI locally to catch issues before GitHub Actions:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy .
uv run pytest
```

All four must pass. If `ruff format --check` fails, run `ruff format .` to fix it.

## Releasing a new version

Until the `/release` skill exists (PR #6), releases are manual:

1. **Bump version:**
   ```bash
   echo "0.X.Y" > VERSION
   ```
   Use semantic versioning: MAJOR.MINOR.PATCH (see [CHANGELOG.md](CHANGELOG.md) for rules).

2. **Update CHANGELOG.md:**
   ```markdown
   ## [Unreleased]

   ### Planned
   - ...

   ## [0.X.Y] - YYYY-MM-DD

   ### Added
   - ...
   ```
   Move the `[Unreleased]` section to a dated release section. Add a new empty `[Unreleased]` at the top.

3. **Commit and tag:**
   ```bash
   git add VERSION CHANGELOG.md
   git commit -m "chore: bump version to 0.X.Y"
   git tag v0.X.Y
   git push origin HEAD
   git push origin v0.X.Y
   ```

4. **GitHub Actions will:**
   - Run `release.yml` workflow on tag push
   - Extract the matching `## [0.X.Y]` section from CHANGELOG
   - Create a GitHub Release with that body
   - Build and push Docker image to GHCR tagged `:0.X.Y` and `:latest`

**Before releasing, ensure:**
- The commit with the version bump is on `main` and all CI is green
- No uncommitted changes (clean working tree)
- You have push access to both the repo and Docker registry

## Common fixes

### "Import block is un-sorted"
```bash
uv run ruff check --fix .
```
Ruff will reorder imports automatically.

### "Line too long"
Ruff won't auto-fix these. Either:
1. Wrap the line:
   ```python
   # Before
   result = some_long_function_name(arg1, arg2, arg3, arg4, arg5)
   
   # After
   result = some_long_function_name(
       arg1, arg2, arg3, arg4, arg5
   )
   ```
2. Or extract to a variable:
   ```python
   long_list = [item1, item2, item3, item4, item5, item6, item7]
   ```

### "Unused import"
```bash
uv run ruff check --fix .
```
Ruff removes them automatically.

### Type errors from mypy
Run with verbose output:
```bash
uv run mypy . --pretty
```
Then add type hints or `# type: ignore` comments where appropriate (sparingly).

## Git workflow

1. Create a feature branch: `git checkout -b feat/your-feature`
2. Make changes and test locally
3. Commit: `git commit -m "feat: description"`
4. Push: `git push -u origin feat/your-feature`
5. Open a PR on GitHub

## When stuck

- `uv sync` — re-sync virtual environment if dependencies seem broken
- `rm -rf .venv` + `uv sync` — hard reset the venv
- Check `.python-version` — should be `3.12`
- Check `pyproject.toml` — the source of truth for deps and tool config

## See also

- [CLAUDE.md](CLAUDE.md) — architecture and security invariants
- [GOALS.md](GOALS.md) — roadmap and long-term vision
- [CHANGELOG.md](CHANGELOG.md) — what changed in each version
