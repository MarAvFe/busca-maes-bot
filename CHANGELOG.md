# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Family tree search: person → parents → grandparents → children → cousins (TSE)
- Vehicle plate lookup via rnpdigital.com (cars and motorcycles)
- Fly.io deployment config

## [0.1.0] - 2026-05-02

### Added
- TSE person search by name (nombre, apellido1, apellido2)
- Returns first match: cédula, full name, date of birth, age, nationality, parents
- Telegram bot with `/buscar`, `/start`, `/help` commands
- Plain-text message handling (no command prefix needed)
- ASP.NET WebForms scraper with full session and ViewState management
