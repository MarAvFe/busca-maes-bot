# BuscaMaes — Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Family tree search: person → parents → grandparents → children → cousins (TSE)
- Vehicle plate lookup via rnpdigital.com (cars and motorcycles)

## [0.6.2] - 2026-05-03

### Changed
- **Allowlist → denylist + abuse detection.** Removed `ALLOWLIST_USER_IDS` env var (everyone access default now). Added `DAILY_ABUSE_THRESHOLD` (default 20 req/day). Users exceeding threshold auto-denied via persistent `denied_users` table in audit DB.
- **@requires_auth decorator removed.** Merged into `@rate_limited`: denial check → token bucket → abuse check.
- **Misuse disclaimer removed** from `/start` and `/help` (trust model now implicit).
- Removed `src/buscamaes/security/allowlist.py` and `tests/test_allowlist.py`.

### Added
- **Daily counter (in-memory)** in `rate_limit.py`. Resets at UTC midnight, restart-amnesty acceptable.
- **Denylist persistence** in `storage/audit.py`: `denied_users` table with `deny_user()`, `is_denied()`, `_list_denied()`.
- **Abuse detection** in decorators: if daily count >threshold → `deny_user()` + audit `auth_denied` with result `abuse_threshold`.
- `tests/test_denylist.py` — 3 tests (deny insert, is_denied true/false, idempotent).
- `tests/test_abuse_detection.py` — 2 tests (under threshold no deny, over threshold deny + DB row).

### Upgrade notes
- Drop `ALLOWLIST_USER_IDS` from `.env` (optional `DAILY_ABUSE_THRESHOLD` if non-default).
- Existing audit DB auto-migrates: `CREATE TABLE IF NOT EXISTS denied_users` on init.
- All existing users (no prior denial) access bot immediately.
- No data loss; audit log unchanged.

## [0.6.1] - 2026-05-03

### Fixed
- **Audit query hash consistency.** `no_results` path was hashing raw input `(query, "", "")` instead of parsed decomposition, breaking audit grouping. Now hashes first decomposition like success paths.
- **Missing `make audit` target.** CHANGELOG promised it; now available on droplet.
- **Dev-friendly audit DB default.** Added comment in `.env.example` showing local override: `AUDIT_DB_PATH=./data/audit.db`.

## [0.6.0] - 2026-05-03

### Added
- **Allowlist** (`ALLOWLIST_USER_IDS` env var). Empty = deny all (fail-closed). Denied users get a polite refusal and an `auth_denied` audit row.
- **Per-user rate limiting** (in-memory token bucket). Defaults: 10 requests / 60s. Configurable via `RATE_LIMIT_MAX` and `RATE_LIMIT_WINDOW`.
- **SQLite audit log** at `/data/audit.db`. Schema: `(ts, user_id, action, query_hash, correlation_id, result)`. Stores **query hashes only**, never raw text. WAL mode. 90-day retention via daily background cleanup task.
- **Misuse disclaimer** in `/start` and `/help`: "Esta herramienta consulta registros públicos. El uso indebido es responsabilidad del usuario."
- New packages: `src/buscamaes/security/` (allowlist, rate_limit, decorators) and `src/buscamaes/storage/` (audit DB).
- New `make audit` target shows the last 20 audit rows.
- 10 new tests (allowlist 3 + rate_limit 4 + audit 3) — total tests: 47.

### Changed
- `__main__.py` opens the audit DB on startup via PTB's `post_init` hook and starts the cleanup background task. Closes connection in `post_shutdown`.
- `docker-compose.yml` mounts `./data:/data` for SQLite persistence across container rebuilds.
- `.env.example` documents the four new env vars.

### Upgrade notes
- **Action required:** set `ALLOWLIST_USER_IDS` in `.env` before deploying, otherwise nobody (including you) can use the bot. Get your Telegram ID from `@userinfobot`.
- Create a `data/` dir in the deployment directory before `docker compose up` (the volume mount expects it). The dir will be auto-created on the host but worth confirming permissions are correct.

## [0.5.0] - 2026-05-03

### Added
- **JSON structured logging** via python-json-logger. Format: `{timestamp, level, logger, message, correlation_id, ...}`
- **Per-request correlation IDs** via `contextvars.ContextVar`. Set at `cmd_buscar` / `handle_text` / `handle_callback` entrypoints. Injected onto every `LogRecord` via `CorrelationIdFilter`.
- **Sentry integration** (sentry-sdk 2.18.0), gated on `SENTRY_DSN` env var. PII off, no performance traces. Release tag = `buscamaes@<version>`.
- `src/buscamaes/observability.py` — correlation ID management, JSON logging config, Sentry init.
- Docker Compose healthcheck (process-level `pgrep`, 30s interval).
- Dockerfile installs `procps` for healthcheck.
- `tests/test_observability.py` — 4 tests (CID generation, filter, JSON output format).

### Changed
- `release.yml`: replaced archived `actions/create-release@v1` with `softprops/action-gh-release@v2`.
- CHANGELOG extractor: `awk` → `sed`. Handles last-version edge case correctly.
- `.env.example` documents `SENTRY_DSN` (optional).

## [0.4.2] - 2026-05-03

### Fixed
- **Input validation was dead code.** `validate_name_query()` existed but was never called from handlers. Wired it into `_do_search()` so queries are checked for length, charset, and emptiness before hitting the scraper.
- **`__version__` breaks when package is installed as wheel.** Switched from Path-walking to `importlib.metadata.version()` so it reads from package metadata instead of a filesystem file that isn't bundled in wheels.
- **Test environment coupling.** `settings.py` ran `load_dotenv()` at import time, forcing all tests to set `BOT_TOKEN` env var. Moved `load_dotenv()` into `Settings.__init__()` and cached `get_settings()` with `@lru_cache` so env is loaded on demand, not at import.

### Changed
- Test files now use absolute imports (`from buscamaes…`) instead of mixed `from src.buscamaes…` form. Dropped `os.environ.setdefault("BOT_TOKEN", …)` boilerplate.
- Cleaned up empty placeholder packages: deleted `storage/`, emptied `bot/__init__.py` and `sources/__init__.py` (no public API exports yet).
- Removed dead `[tool.ruff.lint.per-file-ignores]` entry for deleted `test_scraper.py`.
- One residual f-string logger call (`logger.exception(f"…")`) converted to lazy `%`-style.

## [0.4.1] - 2026-05-03

### Security
- **Stop logging raw user names.** All TSE search log lines now emit `query_hash` (16-char sha256) instead of `nombre`/`apellido` values, restoring GOALS.md key invariant #1.
- `LOG_LEVEL` env var (default `INFO`) replaces hardcoded `DEBUG` in `__main__.py`. Add `LOG_LEVEL=DEBUG` to `.env` for local debugging.
- Errors shown to users now flow through `sanitize_user_error()` instead of leaking raw exception strings.

### Added
- `src/buscamaes/logging_utils.py` with `query_hash()` helper.
- `tests/test_tse_parser.py` — 8 tests covering `_extract_viewstate`, `_parse_delta`, `_parse_results_list` (regression for commit 0b62237), `_parse_resultado`.
- `tests/test_validation.py` — 10 tests covering `validate_name_query` and `sanitize_user_error`.

### Changed
- All `logger.debug(f"...")` / `logger.info(f"...")` calls converted to `%`-style formatting (lazy evaluation).
- `cmd_start` / `cmd_help` use `buscamaes.__version__` instead of walking the filesystem to find VERSION.

### Removed
- Backward-compat shims `bot.py` and `tse_scraper.py` at repo root. These imported via `from src.buscamaes…` which only worked from the repo root and not from any installed context. Use `python -m buscamaes` (already the Docker entrypoint).

## [0.4.0] - 2026-05-03

### Added
- Code restructure into `src/buscamaes/` package: `bot/`, `sources/tse/`, `storage/`
- `src/buscamaes/sources/tse/` splits scraper into `models.py`, `parser.py`, `client.py`
- `src/buscamaes/bot/` splits handlers into `handlers.py`, `formatting.py`
- `src/buscamaes/__main__.py` entry point for `python -m buscamaes`
- `src/buscamaes/settings.py` environment variable loader
- `src/buscamaes/validation.py` input validation and sanitization stubs
- `pyproject.toml` build system configuration with hatchling, dynamic version from VERSION file

### Changed
- Dockerfile: `CMD` changed to `["uv", "run", "python", "-m", "buscamaes"]`
- Backward-compat shims in `bot.py` and `tse_scraper.py` import from new locations
- `requires-python` bumped to >=3.12 in pyproject.toml
- Tests updated to import from new package structure

## [0.3.0] - 2026-05-03

### Added
- `pyproject.toml` replacing `requirements.txt`; dependency management via uv with lockfile
- `.python-version` pinning Python 3.12
- Initial test suite (pytest): name parsing, session expiry, VERSION format
- GitHub Actions CI: lint (ruff), type check (mypy), tests (pytest) on every PR and push to main
- GOALS.md capturing the long-term SDLC roadmap

### Changed
- Dockerfile now uses uv for dependency installation (faster, reproducible builds)
- README updated with uv setup instructions and improved DigitalOcean deploy guide
- Bot UX voice: consistent voseo Spanish (Escribí, podés, etc.)
- README version badge: 0.2.0 → 0.3.0
- Tool cache directories (.mypy_cache, .ruff_cache, .pytest_cache) added to .gitignore

### Added (Documentation)
- Release procedure documented in CONTRIBUTING.md (manual process until `/release` skill in PR #6)
- GOALS.md milestone M1.5: release policy and documentation

## [0.2.0] - 2026-05-02

### Added
- Multiple results: inline keyboard showing up to 5 choices with cédula and full name
- Header shows total result count and how many fallecidos were hidden
- "FALLECIDO" entries filtered from choices (counted but not shown)
- "Abrir en TSE" button links to the TSE search page for manual refinement
- "Cancelar" button to dismiss the search
- Pending sessions expire after 5 minutes

### Changed
- Scraper split into `search_session()` + `select_from_session()` for reuse
- `search_person()` kept as a convenience wrapper (auto-selects first alive result)

## [0.1.0] - 2026-05-02

### Added
- TSE person search by name (nombre, apellido1, apellido2)
- Returns first match: cédula, full name, date of birth, age, nationality, parents
- Telegram bot with `/buscar`, `/start`, `/help` commands
- Plain-text message handling (no command prefix needed)
- ASP.NET WebForms scraper with full session and ViewState management
