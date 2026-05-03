# busca-maes-bot — Claude Code Guidelines

## Model Usage Policy

### Opus (Planning & Architecture)
**When to use:**
- Architecture decisions
- Security design
- Feature planning
- Code reviews/audits

**Output format:**
- Design specs ONLY
- No implementation code
- Explain: what, why, key decisions
- Structure: files, functions, dependencies

**Settings:**
- Effort: High
- Extended Thinking: ON (for complex decisions)
- Caveman: OFF

**Example output:**

```
Feature: User Authentication
Design:

JWT tokens, 24h expiration
bcrypt for password hashing (cost=12)
Redis for token revocation list

Files:

auth.py: hash_password(), verify_password(), generate_token()
middleware.py: verify_jwt() decorator

Key decisions:

JWT over sessions (stateless, scales better)
Revocation list for instant logout (security > pure stateless)

[NO CODE - specs only]
```

---

### Haiku (Implementation)
**When to use:**
- Implementing from Opus specs
- Bug fixes (non-architectural)
- Refactoring
- Test writing

**Input:**
- Receive Opus design spec
- Follow it exactly

**Output format:**
- Code implementation
- Minimal comments (code speaks)
- Caveman mode ON (full or ultra)

**Settings:**
- Extended Thinking: Off
- Caveman: FULL or ULTRA

---

## Workflow

### New Feature
1. **Opus:** Design the feature (spec only)
2. **Haiku:** Implement per spec
3. **Opus:** Review implementation

### Bug Fix
- Simple: Haiku directly
- Complex: Opus diagnoses → Haiku fixes

### Refactor
- Haiku (following existing patterns)

---

## Code Conventions

### File Structure

```
src/buscamaes/
init.py
handlers/       # Telegram update handlers
middleware/     # Auth, rate limiting, correlation ID
services/       # Business logic (search, scrape)
models/         # Data models
observability.py
config.py
```

### Logging
- Use correlation IDs (from observability.py)
- Structured JSON logs
- Include: timestamp, level, logger, message, correlation_id

### Error Handling
- Never expose internal errors to users
- Log full traceback
- Return generic message to Telegram
- Sentry for production errors

### Security
- No secrets in code (env vars only)
- Rate limit all user-facing endpoints
- Sanitize all user input
- HTTPS only for webhooks

---

## Prohibited Actions
- [ ] Writing secrets/tokens to logs
- [ ] Exposing stack traces to users
- [ ] Committing .env files
- [ ] Skipping input validation
- [ ] Using eval() or exec()

---

## Dependencies
- python-telegram-bot (async)
- python-json-logger
- sentry-sdk (optional)
- redis (for rate limiting)

---

## Testing
- pytest for all business logic
- Mock Telegram API calls
- Run tests before commit (future: pre-commit hook)
- before validating ruff, run ruff format first
