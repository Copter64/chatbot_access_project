# Contributing

Thank you for your interest in contributing to the Discord Game Server Access Bot.

---

## Getting Started

```bash
git clone https://github.com/Copter64/chatbot_access_project.git
cd chatbot_access_project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
cp .env.example .env   # fill in your values
```

---

## Development Workflow

### Pre-commit hooks

Install once:
```bash
pre-commit install
```

All hooks run automatically on `git commit`. To run manually:
```bash
pre-commit run --all-files
```

Hooks enforced:
- **black** — code formatting (88-char line length)
- **flake8** — linting
- **isort** — import ordering (`profile = "black"`)
- **bandit** — static security analysis
- **detect-secrets** / **detect-private-key** — secret scanning
- Standard file hygiene (trailing whitespace, YAML/JSON validity, merge conflicts)

### Running tests

```bash
python -m pytest tests/ -v
```

All 174 tests must pass. Write or update tests for every change.

### Code standards

- Follow PEP 8; Black is enforced at 88 characters
- All public functions, classes, and modules must have **docstrings**
- Use **type hints** on all function signatures
- Never call `os.getenv()` outside `config.py`
- Never hardcode credentials, IPs, or ports — use `Config` values
- Use `utils/logger.py` for all logging — no bare `print()` in runtime code

---

## Making Changes

1. Create a feature branch: `git checkout -b feature/my-change`
2. Make your changes, write tests, verify all hooks pass
3. Open a pull request with a clear description of what and why
4. Ensure `pytest` and `pre-commit run --all-files` both pass in CI

---

## Module Boundaries

| Module | Responsibility |
|---|---|
| `discord_modules/` | Discord interactions only — no business logic |
| `database/models.py` | All DB access — no raw SQL outside this file |
| `unifi_modules/` | Unifi API only — catch all network errors here |
| `web/` | HTTP request/response — delegate to DB and Unifi modules |
| `utils/` | Shared helpers only (logger, token generator) |
| `config.py` | All `os.getenv()` calls — single source of truth |

---

## Secrets Policy

- **Never commit real credentials** — the repository is public
- `.env` is gitignored; only `.env.example` (with placeholders) is committed
- `detect-secrets` and `detect-private-key` pre-commit hooks are active
- For production: use Docker secrets or an external secret manager

---

## Reporting Bugs

Open a GitHub issue with:
- Steps to reproduce
- Expected vs. actual behaviour
- Relevant log output (redact any credentials)
