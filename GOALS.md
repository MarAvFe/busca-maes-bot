# BuscaMaes — Goals & Roadmap

## Vision

BuscaMaes is a private Telegram bot that lets a small, trusted group (~100 users) do quick lookups against Costa Rica's public government databases — starting with the TSE electoral registry for person-name searches, and expanding to the national vehicle plate registry. The goal is to maintain a professional-grade SDLC that keeps the codebase easy to extend, safe to operate, and auditable — without the overhead that a large-scale project would require.

---

## Current state (v0.2.0)

- ✅ TSE person-name search with multiple-result selection
- ✅ Semver + Keep-a-Changelog
- ✅ Dockerized deployment (DigitalOcean droplet)
- ✅ Tooling foundation: uv, ruff, mypy, pytest, GitHub Actions CI
- ⬜ Code restructure into `src/buscamaes/` package
- ⬜ JSON structured logging + Sentry error tracking
- ⬜ Automated git-tag releases
- ⬜ Security middleware (allowlist, rate limiting, input validation, audit log)
- ⬜ TSE upstream resilience (retries, circuit breaker)
- ⬜ Claude Code tooling (CLAUDE.md, skills, agents, hooks)
- ⬜ Vehicle plate registry integration

---

## Roadmap

### M1 — Tooling foundation ✅ `v0.3.0`
- [x] `pyproject.toml` + `uv.lock` replacing `requirements.txt`
- [x] ruff (lint + format) + mypy (type check)
- [x] pytest with initial test suite
- [x] GitHub Actions CI: lint / typecheck / test on every PR and push to main

### M2 — Code restructure ⬜ `v0.4.0`
- [ ] Reorganize into `src/buscamaes/{bot,sources/tse,storage,resilience}/`
- [ ] `Container` dataclass for dependency injection
- [ ] `settings.py` for env loading and validation
- [ ] Unit tests for TSE parser and formatting using captured HTML fixtures
- [ ] Docker and CI smoke test updated

### M3 — Observability + release automation ⬜ `v0.5.0`
- [ ] JSON structured logging with per-request correlation IDs
- [ ] Sentry integration (gated on `SENTRY_DSN` env var)
- [ ] Docker Compose healthcheck
- [ ] GitHub Actions release workflow: tag → extract CHANGELOG section → GH Release + GHCR image

### M4 — Security middleware ⬜ `v0.6.0`
- [ ] Telegram user ID allowlist (`ALLOWLIST_USER_IDS` env var)
- [ ] Per-user rate limiting (in-memory token bucket)
- [ ] Input validation: length cap, character allowlist, sanitized error messages
- [ ] SQLite audit log (`/data/audit.db`) — stores query hashes, not raw text; 90-day retention
- [ ] Misuse disclaimer in `/start` and `/help`

### M5 — Resilience ⬜ `v0.7.0`
- [ ] Tenacity retry policy around TSE HTTP calls (3 tries, exponential backoff)
- [ ] Circuit breaker for TSE outages
- [ ] Integration test simulating TSE 503/timeout via `respx`

### M6 — Claude Code tooling ⬜ `v0.8.0`
- [ ] `CLAUDE.md` — project conventions, security invariants, prohibited actions
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

## How to update this file

When a milestone is shipped, check its boxes and move to `[Unreleased]` in `CHANGELOG.md` via the `/release` skill (available from M6 onwards).
