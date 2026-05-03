# BuscaMaes — Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Family tree search: person → parents → grandparents → children → cousins (TSE)
- Vehicle plate lookup via rnpdigital.com (cars and motorcycles)

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
