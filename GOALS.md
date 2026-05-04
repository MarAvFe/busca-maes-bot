# BuscaMaes — Goals & Roadmap

## Vision

BuscaMaes is a private Telegram bot that lets a small, trusted group (~100 users) do quick lookups against Costa Rica's public government databases — starting with the TSE electoral registry for person-name searches, and expanding to the national vehicle plate registry. The goal is to maintain a professional-grade SDLC that keeps the codebase easy to extend, safe to operate, and auditable — without the overhead that a large-scale project would require.

---

## Current state (v0.7.0)

- ✅ TSE person-name search with multiple-result selection
- ✅ RNP vehicle plate search (cars, motorcycles, cargo trucks)
- ✅ Semver + Keep-a-Changelog
- ✅ Dockerized deployment (DigitalOcean droplet)
- ✅ Tooling foundation: uv, ruff, mypy, pytest, GitHub Actions CI
- ✅ Release policy: version bumps, CONTRIBUTING.md docs
- ✅ Code restructure into `src/buscamaes/` modular package
- ✅ Security hygiene: stop logging raw queries, input validation, error sanitization
- ✅ JSON structured logging + Sentry error tracking + correlation IDs
- ✅ Automated git-tag releases (release.yml: tag → GH Release + GHCR image)
- ✅ Security middleware (denylist + abuse detection, rate limiting, audit log)
- ✅ RNP test coverage (59 tests, full ROT/SMELL hardening)
- ⬜ TSE upstream resilience (retries, circuit breaker)
- ⬜ Claude Code tooling (CLAUDE.md, skills, agents, hooks)

---

## Roadmap

### M1 — Tooling foundation ✅ `v0.3.0`
- [x] `pyproject.toml` + `uv.lock` replacing `requirements.txt`
- [x] ruff (lint + format) + mypy (type check)
- [x] pytest with initial test suite
- [x] GitHub Actions CI: lint / typecheck / test on every PR and push to main

### M1.5 — Release policy ✅ `v0.3.0`
- [x] README version badge updated to match VERSION file
- [x] Release procedure documented in CONTRIBUTING.md
- [x] Tool caches (.mypy_cache, .ruff_cache, .pytest_cache) added to .gitignore

### M2 — Code restructure ✅ `v0.4.0`
- [x] Reorganize into `src/buscamaes/{bot,sources/tse,storage,resilience}/`
- [x] `settings.py` for env loading and validation
- [x] Modular layout with backward-compat shims for import compatibility
- [x] Dockerfile updated to `["uv", "run", "python", "-m", "buscamaes"]`
- [x] All tests passing; lint/format/typecheck green

### M2.5 — Security hygiene audit ✅ `v0.4.1`
- [x] Stop logging raw query input (sha256 hash only)
- [x] Lazy-eval all logger calls (% formatting, not f-strings)
- [x] Add unit tests for scraper parsers (18 new tests, 33 total)
- [x] Wire sanitize_user_error() into error paths
- [x] LOG_LEVEL env var, default INFO (not DEBUG)

### M2.6 — M2 audit cleanup ✅ `v0.4.2`
- [x] Wire `validate_name_query()` into handlers (was dead code)
- [x] Switch `__version__` to `importlib.metadata` (path-walk breaks in wheels)
- [x] Fix test import coupling: `settings.py` ran `load_dotenv()` at import time
- [x] Standardize test imports: absolute `from buscamaes…` vs. mixed `from src.buscamaes…`
- [x] Delete empty `storage/` placeholder package
- [x] Clean up `pyproject.toml` (dead per-file-ignores)
- [x] Empty `bot/__init__.py` and `sources/__init__.py` (no public API exports yet)

### M3 — Observability + release automation ✅ `v0.5.0`
- [x] JSON structured logging with per-request correlation IDs
- [x] Sentry integration (gated on `SENTRY_DSN` env var)
- [x] Docker Compose healthcheck (process-level via pgrep)
- [x] GitHub Actions release workflow: tag → extract CHANGELOG section → GH Release + GHCR image

### M4 — Security middleware ✅ `v0.6.2`
- [x] Denylist + abuse detection (everyone access default; auto-deny >20 req/day)
- [x] Per-user rate limiting (in-memory token bucket, 10 req/60s)
- [x] SQLite audit log (`/data/audit.db`) — stores query hashes only; 90-day retention
- [x] Persistent denied_users table for abuse quarantine
- [x] Daily counter (in-memory, UTC midnight reset)
- (Input validation already shipped in M2.6)

### M5 — RNP vehicle plate search ✅ `v0.7.0`
- [x] RNP scraper (lazy login, session reuse, expiry retry)
- [x] Plate format detection (6 patterns: auto numeric/alpha, MOT, CL)
- [x] JSF/RichFaces HTML parser (ViewState, argus, vehicle fields)
- [x] Markdown-safe formatting (escape special chars)
- [x] Full test coverage (59 tests: detection, parser, client, formatting, handler)
- [x] ROT/SMELL hardening (login detection, session reset, row-driven parser)

### M6 — Resilience ⬜ `v0.8.0`
- [ ] Tenacity retry policy around TSE HTTP calls (3 tries, exponential backoff)
- [ ] Circuit breaker for TSE outages
- [ ] Integration test simulating TSE 503/timeout via `respx`

### M6 — Claude Code tooling ⬜ `v0.8.0`
- [ ] `CLAUDE.md` — project conventions, security invariants, prohibited actions; **model policies: Opus full output, Haiku caveman mode**
- [ ] `.claude/settings.json` — hook to auto-enable caveman (full intensity) when Haiku is invoked
- [ ] `.claude/skills/release/` — `/release` skill automates VERSION bump + CHANGELOG promotion + PR
- [ ] `.claude/skills/add-data-source/` — scaffolds a new registry integration
- [ ] `.claude/agents/scraper-reviewer.md` — reviews TSE/scraper changes for regressions
- [ ] `.claude/agents/security-reviewer.md` — reviews handler/middleware changes for security
- [ ] `.claude/hooks/` — enforces CHANGELOG entry on user-facing changes, pytest on stop
- [ ] GitHub Actions docker build + smoke test workflow

### M7+ — Future ⬜
- [ ] Vehicle plate lookup via rnpdigital.com (cars and motorcycles) — use `/add-data-source plates`
- [ ] Family tree search: person → parents → grandparents → children (TSE)

---

## Non-goals

- **Horizontal scaling** — single droplet is sufficient; rate limiting is intentionally in-memory
- **Database beyond SQLite** — Redis/Postgres would add ops overhead for no gain at this scale
- **Public marketing** — bot stays private/invite-only by design
- **MCP servers** — deferred; not needed for current workflow

---

## Key invariants

These must hold at every PR:

1. **Never log raw query input** — only `sha256(query)[:16]` hash in audit log
2. **Never bypass middleware** — middleware order is `correlation_id → allowlist → rate_limit → validate → handler → audit`
3. **Never widen `sanitize_user_error()`** — tracebacks go to Sentry, not to users
4. **Never store PII beyond 90-day retention window** — audit log only
5. **User-facing changes require a CHANGELOG `[Unreleased]` entry and a VERSION bump**

---

## Known limitations

- **Callback clicks consume rate-limit + daily quota.** Each button click is a separate update → token + daily count. Search → 5 buttons → click = 2 quota units for 1 intent. Threshold=20 req/day = ~10 searches/day. Acceptable v1; defer callback exemption to M5 when usage data exists.
- **Denylist requires manual SQL recovery.** Operator auto-denied at threshold needs raw `sqlite3 /data/audit.db "DELETE FROM denied_users WHERE user_id=X"`. No operator bypass list yet. Acceptable for single-operator bot.

---

## How to update this file

When a milestone is shipped, check its boxes and move to `[Unreleased]` in `CHANGELOG.md` via the `/release` skill (available from M6 onwards).
