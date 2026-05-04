# BuscaMaesBot

[![Version](https://img.shields.io/badge/version-0.7.0-blue)](CHANGELOG.md)

Telegram bot that searches the Costa Rica Tribunal Supremo de Elecciones (TSE) electoral registry for people by name, and the Registro Nacional de Personas (RNP) for vehicle plates.

## How it works

### TSE person search
The bot replicates the browser flow on `servicioselectorales.tse.go.cr`:

1. Fetches a fresh VIEWSTATE from the search form
2. Submits an AJAX search with the name parts
3. Parses the ASP.NET delta response to follow the redirect to the results list
4. Selects the first result and follows the redirect to the person detail page
5. Parses and returns the person's data

### RNP vehicle plate search
For plate lookups, the bot authenticates to `rnpdigital.com` and scrapes vehicle data:

1. Logs in once with configured credentials (reused across queries)
2. Detects session expiry and re-authenticates automatically
3. Submits a plate query through the JSF form interface
4. Parses HTML response and extracts vehicle metadata
5. Returns a single-line summary (placa, marca, estilo, año, cc, valor, propietario)

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) — fast Python package manager
- A Telegram bot token (get one from [@BotFather](https://t.me/BotFather))

## Setup

```bash
# Install uv (once)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Create your .env file
cp .env.example .env
```

Edit `.env` and set your bot token:

```
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxYZ
```

## Running

Start the bot:

```bash
uv run python -m buscamaes
```

## Testing

```bash
uv run pytest
```

## Usage

### Person search (TSE)

Send any message to the bot with a name to search. The last two words are treated as the two apellidos, everything before is the nombre.

| Input | nombre | apellido1 | apellido2 |
|---|---|---|---|
| `juan mora fernandez` | juan | mora | fernandez |
| `maria jose mora fernandez` | maria jose | mora | fernandez |
| `juan mora` | juan | mora | — |

Or use the `/buscar` command:

```
/buscar juan mora fernandez
```

### Vehicle plate search (RNP)

Send a single word (no spaces) to search for a vehicle plate. Supported formats:

| Format | Example |
|---|---|
| 6 digits (auto) | `621335` |
| 3 letters + 3 digits (auto) | `BJV123` |
| Light cargo | `CL123456` |
| Motorcycle (M + digits) | `M621335` |
| Motorcycle (MOT + digits) | `MOT621335` |
| Motorcycle (M + digits + letters) | `M123ABC` |

Or use the `/placa` command:

```
/placa 621335
/placa BJV123
```

### Commands

| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Usage instructions |
| `/buscar <name>` | Search person by name (TSE) |
| `/placa <plate>` | Search vehicle by plate (RNP) |

## Deploying to DigitalOcean

The cheapest Droplet ($6/month, 1 vCPU / 1 GB RAM) is more than enough.

**1. Create a Droplet**
Choose Ubuntu 24.04, the $6 basic plan, and add your SSH key.

**2. Install Docker on the Droplet**
```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker $USER && newgrp docker
```

**3. Clone the repo and configure**
```bash
git clone git@github.com:maravfe/busca-maes-bot.git
cd busca-maes-bot
cp .env.example .env
nano .env   # paste your BOT_TOKEN
```

**4. Run**
```bash
docker compose up -d --build
```

The `restart: unless-stopped` policy in `docker-compose.yml` keeps the bot alive across reboots and crashes.

**5. Verify it's running**
```bash
docker compose ps           # should show "running"
docker compose logs -f      # watch live logs
```

**Deploying a new version**
```bash
git pull
docker compose up -d --build
```

**Other useful commands**
```bash
docker compose logs -f      # live logs
docker compose restart      # restart without rebuilding
docker compose down         # stop
```

## Versioning

This project uses [Semantic Versioning](https://semver.org/):

- **MAJOR** — breaking change (e.g. renamed commands, restructured output)
- **MINOR** — new feature, backwards compatible (e.g. family tree search, plate lookup)
- **PATCH** — bug fix or scraper adjustment (e.g. TSE changed their HTML)

When releasing a new version, update `VERSION` and add an entry to `CHANGELOG.md`.

## Roadmap

See [GOALS.md](GOALS.md) for the full roadmap and long-term goals, and [CHANGELOG.md](CHANGELOG.md) for release history.

## Notes

- When multiple results are found, the bot shows up to 5 choices as inline buttons, ranked by exact-word match.
- The TSE site supports partial name matching — you can search with just a first name or just apellidos.
- If the scraper returns empty fields after a successful search, run `test_scraper.py` with debug logging and inspect the HTML structure of `resultado_persona.aspx` to adjust `_parse_resultado` in `tse_scraper.py`.
