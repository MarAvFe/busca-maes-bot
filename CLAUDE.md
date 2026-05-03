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

#### Opus is FORBIDDEN from writing:
- ❌ Full file contents (raw code)
- ❌ Exact Edit/Write tool calls or arguments
- ❌ Line-by-line code diffs
- ❌ Step-by-step "do this then this" sequences
- ❌ old_string/new_string blocks
- ❌ Prescriptive implementation plans (Step 1: ..., Step 2: ...)
- ❌ Exact function signatures with bodies (only skeleton in spec)
- ❌ Detailed test expectations (only test coverage goals)

**ENFORCEMENT:** If a draft spec exceeds ~100 lines or contains code blocks larger than 5 lines, STOP. Use EnterPlanMode only for design decisions, NOT for implementation roadmaps. A spec is: **files + function names + signatures (params/return only) + decisions + why.** Implementation is Haiku's job.

**Red flags:** "old_string", "new_string", numbered steps with edits, "replace entire file", tool call parameters. If you see these, the spec is implementation, not design.

**Example: correct spec (~50 lines)**
```
M4 Design — Allowlist + Rate Limit

Goal: Prevent casual misuse via deny-list and per-user quota.

Architecture:
Middleware stack: correlation_id → allowlist → rate_limit → validate → handler → audit
Order: deny-listed users must not consume bucket.

Allowlist:
- ALLOWLIST_USER_IDS env var (comma-separated user IDs)
- Empty = deny all (fail-closed)
- Function: is_allowed(user_id: int) -> bool

Rate Limit:
- Token bucket: default 10 req/60s per user
- In-memory (restart = reset)
- Function: check_and_consume(user_id, max, window) -> bool

Files:
- src/buscamaes/security/allowlist.py — is_allowed()
- src/buscamaes/security/rate_limit.py — check_and_consume()
- src/buscamaes/security/decorators.py — @requires_auth, @rate_limited

Modify:
- handlers.py: decorate all handlers with @requires_auth, @rate_limited
- settings.py: add allowlist + rate_limit config
- __main__.py: wire decorator imports

Testing:
- Allowlist: monkeypatch get_settings(), test empty vs. populated
- Rate limit: mock time.monotonic() for refill test
```

This is good. Code skeleton only, no full file contents, no prescriptive steps.

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
1. **Opus:** Design the feature (spec only) → use `ExitPlanMode` to request approval
2. **User:** Reviews and approves plan before implementation starts
3. **Haiku:** Implement per spec
4. **Opus:** Review implementation

### Bug Fix
- Simple: Haiku directly
- Complex: Opus diagnoses → Haiku fixes

### Refactor
- Haiku (following existing patterns)

---

## Plan Mode Enforcement

**Opus uses `EnterPlanMode` for architectural decisions.** When a spec is ready:
1. Call `ExitPlanMode` to signal completion (triggers user approval gate)
2. User reviews the plan in `.claude/plans/`
3. User approves or requests changes
4. Only after approval: Haiku implements

**Hook enforcement:** `.claude/hooks/plan-spec-enforcer.js` blocks any Write to `plans/*` that:
- Exceeds 100 lines
- Contains code blocks > 5 lines
- Contains `old_string`/`new_string`, step sequences, or "replace entire file"

If the hook blocks, the spec is too implementation-heavy. Haiku's job, not Opus's.

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
