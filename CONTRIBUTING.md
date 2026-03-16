# Contributing to Hashed SDK

Thank you for your interest in contributing! Hashed is an open-source project and we welcome improvements of all kinds — bug reports, documentation fixes, new features, and test coverage.

---

## 📋 Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How to Report a Bug](#how-to-report-a-bug)
- [How to Propose a Feature](#how-to-propose-a-feature)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Pull Request Process](#pull-request-process)
- [Code Style](#code-style)
- [Commit Convention](#commit-convention)

---

## Code of Conduct

This project follows a simple rule: be respectful and constructive. Harassment, discrimination, or personal attacks will result in removal from the project.

---

## How to Report a Bug

1. **Check existing issues** first: [github.com/Josoriop9/IAMandagent/issues](https://github.com/Josoriop9/IAMandagent/issues)
2. If not already reported, open a new issue with:
   - **Title**: concise description (e.g., `guard() decorator raises AttributeError when agent_id is None`)
   - **Environment**: Python version, OS, `hashed-sdk` version (`pip show hashed-sdk`)
   - **Minimal reproducer**: the smallest code snippet that triggers the bug
   - **Expected vs actual behavior**
   - **Traceback** (full stack trace if applicable)

> **Security vulnerabilities** must NOT be reported via GitHub Issues.  
> See [SECURITY.md](SECURITY.md) for the responsible disclosure process.

---

## How to Propose a Feature

1. Open a GitHub Issue with the `enhancement` label
2. Describe:
   - **Problem**: What user need or gap does this address?
   - **Proposed solution**: High-level approach
   - **Alternatives considered**: Why not the alternatives?
   - **Breaking changes**: Would this change existing public API?
3. Wait for a maintainer to approve the design before submitting a PR — this prevents wasted effort on rejected approaches

---

## Development Setup

### Prerequisites

- Python 3.9 or newer
- `git`

### Steps

```bash
# 1. Fork the repo on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/IAMandagent.git
cd IAMandagent

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 3. Install the SDK in editable mode + dev dependencies
pip install -e ".[dev]"

# 4. Verify installation
python -c "import hashed; print(hashed.__version__)"
hashed --help
```

### Optional: Backend + Dashboard

For contributions touching the server or dashboard:

```bash
# Backend (FastAPI)
cd server
pip install -r requirements.txt
cp .env.example .env  # fill in your Supabase credentials
python server.py

# Dashboard (Next.js)
cd dashboard
npm install
npm run dev
```

---

## Running Tests

```bash
# All tests with coverage report
pytest

# Specific test file
pytest tests/test_guard.py -v

# Specific test
pytest tests/test_circuit_breaker.py::test_circuit_opens_after_threshold -v

# With coverage threshold (same as CI)
pytest --cov=src/hashed --cov-fail-under=65
```

**Current coverage gate:** 65% (enforced in CI — PRs that drop below this threshold will fail).

---

## Pull Request Process

### Branch Naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feature/<short-description>` | `feature/wal-ledger` |
| Bug fix | `fix/<short-description>` | `fix/guard-none-agent-id` |
| Documentation | `docs/<short-description>` | `docs/contributing-guide` |
| Refactor | `refactor/<short-description>` | `refactor/core-srp` |
| Tests | `test/<short-description>` | `test/circuit-breaker-coverage` |

### PR Checklist

Before opening a PR, confirm:

- [ ] All tests pass locally: `pytest`
- [ ] Linter passes: `ruff check src/ tests/`
- [ ] Type checker passes: `mypy src/hashed/`
- [ ] Formatter passes: `black --check src/ tests/`
- [ ] New code has tests (coverage should not drop)
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if behavior changes
- [ ] `SPEC.md` updated if protocol behavior changes

### Review Process

1. Open PR against `main`
2. CI runs automatically (ruff + mypy + pytest + docker build)
3. At least one maintainer must approve
4. Maintainer merges (squash merge for features, regular merge for releases)

---

## Code Style

This project uses:

| Tool | Purpose | Run |
|------|---------|-----|
| **black** | Code formatter | `black src/ tests/` |
| **ruff** | Linter (replaces flake8 + isort) | `ruff check src/ tests/` |
| **mypy** | Static type checker | `mypy src/hashed/` |

All three are enforced in CI. Configuration lives in `pyproject.toml`.

**Key conventions:**
- Type hints on all public functions
- Docstrings on all public classes and methods (Google style)
- No `print()` in library code — use `logging.getLogger(__name__)`
- Async functions for I/O-bound operations
- `raise X from e` (not bare `raise X`) when re-raising exceptions

---

## Commit Convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]
[optional footer]
```

**Types:**

| Type | When to use |
|------|------------|
| `feat` | New feature visible to users |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Code change with no behavior change |
| `test` | Adding or fixing tests |
| `chore` | Build, CI, dependency updates |
| `perf` | Performance improvement |

**Examples:**
```
feat(guard): add fail-closed mode via HASHED_FAIL_CLOSED env var
fix(ledger): flush buffer on graceful shutdown
docs(readme): add 3-line demo and quick install section
test(circuit-breaker): add 28 tests for all FSM transitions
chore(release): bump version 0.3.0 → 0.3.1
```

---

## Questions?

- **General questions**: [GitHub Discussions](https://github.com/Josoriop9/IAMandagent/discussions)
- **Bug reports**: [GitHub Issues](https://github.com/Josoriop9/IAMandagent/issues)
- **Security**: [SECURITY.md](SECURITY.md)

---

*Thank you for making Hashed better!* 🔐
