# DiayQuién

[![Version](https://img.shields.io/badge/version-0.1.0-orange)](CHANGELOG.md)

Telegram bot that searches for a person in the Costa Rica Tribunal Supremo de Elecciones (TSE) electoral registry by name.

## How it works

The bot replicates the browser flow on `servicioselectorales.tse.go.cr`:

1. Fetches a fresh VIEWSTATE from the search form
2. Submits an AJAX search with the name parts
3. Parses the ASP.NET delta response to follow the redirect to the results list
4. Selects the first result and follows the redirect to the person detail page
5. Parses and returns the person's data

## Requirements

- Python 3.11+
- A Telegram bot token (get one from [@BotFather](https://t.me/BotFather))

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Create your .env file
cp .env.example .env
```

Edit `.env` and set your bot token:

```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

## Running

Test the scraper first (no Telegram needed):

```bash
python test_scraper.py
```

Start the bot:

```bash
python bot.py
```

## Usage

Send any message to the bot with a name to search. The last two words are treated as the two apellidos, everything before is the nombre.

| Input | nombre | apellido1 | apellido2 |
|---|---|---|---|
| `ignacio avila feoli` | ignacio | avila | feoli |
| `maria jose avila feoli` | maria jose | avila | feoli |
| `ignacio avila` | ignacio | avila | — |

You can also use the `/buscar` command:

```
/buscar ignacio avila feoli
```

### Other commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Usage instructions |
| `/buscar <name>` | Search by name |

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking change (e.g. renamed commands, restructured output)
- **MINOR** — new feature, backwards compatible (e.g. family tree search, plate lookup)
- **PATCH** — bug fix or scraper adjustment (e.g. TSE changed their HTML)

When releasing a new version, update `VERSION` and add an entry to `CHANGELOG.md`.

## Roadmap

See [CHANGELOG.md](CHANGELOG.md) for planned features.

## Notes

- Only the **first result** is returned when there are multiple matches.
- The TSE site supports partial name matching — you can search with just a first name or just apellidos.
- If the scraper returns empty fields after a successful search, run `test_scraper.py` with debug logging and inspect the HTML structure of `resultado_persona.aspx` to adjust `_parse_resultado` in `tse_scraper.py`.
