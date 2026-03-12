# CI Pipeline

This project uses GitHub Actions for continuous integration. The pipeline is
defined in `.github/workflows/ci.yml` and runs three jobs.

---

## When Each Job Runs

| Job        | Push to any branch | PR to `master` |
|------------|--------------------|----------------|
| `Lint`     | ✅ always          | ✅ always      |
| `Test`     | ⏭ skipped         | ✅ required    |
| `Security` | ⏭ skipped         | ✅ required    |

Lint runs on every branch push so formatting issues are caught before a PR is
opened. Test and Security are gated to PRs only — they form the merge
quality bar.

---

## Jobs

### Lint (all branches)

Runs formatting and style checks using Python 3.12. Fails fast if any check
fails.

| Step | Tool | What it checks |
|------|------|----------------|
| Format | `black --check --diff` | Consistent code formatting (88-char line length) |
| Imports | `isort --check-only --diff` | Import ordering (black-compatible profile) |
| Style | `flake8` | PEP 8 violations + docstring checks (config in `.flake8`) |

### Test (PR to master only)

Runs the full pytest suite with coverage reporting against Python 3.12.

- Requires `Lint` to pass first (`needs: lint`)
- Produces `coverage.xml`, uploaded as a workflow artifact (retained 7 days)
- A failing `Test` job blocks the PR merge once branch protection is configured

> **Note on Python version matrix**: The project targets Python 3.10+. If
> cross-version compatibility becomes a concern, add a scheduled nightly
> workflow that runs the suite against 3.10, 3.11, and 3.12. Expanding the PR
> matrix slows down every merge — a nightly is the right tradeoff.

### Security (PR to master only)

Runs two independent scans against Python 3.12. Requires `Lint` to pass first.

| Step | Tool | Behaviour on failure |
|------|------|----------------------|
| Static analysis | `bandit -ll` | **Fails the job** — blocks merge |
| Dependency CVEs | `safety check` | Advisory only (`continue-on-error: true`) |

`bandit` excludes `tests/` and virtual environment directories and skips
`B104` (binding to all interfaces — expected in the Flask dev server).

`safety` results should be reviewed periodically even though they don't fail
the build. A vulnerable dependency that never blocks CI is easy to forget.

---

## Enforcing Merge Protection

The workflow file alone does not block merges — GitHub branch protection rules
are required.

### Recommended settings for `master`

> **Prerequisites**: The status check names (`Lint`, `Test`) only appear in
> GitHub's search box after the workflow has run at least once. Push the
> `.github/workflows/ci.yml` file to master first, wait for the Actions run to
> complete, then come back and configure the protection rule.

1. Go to **GitHub → Settings → Branches**
2. Click **Add branch protection rule**
3. Set **Branch name pattern** to `master`
4. Enable:
   - ✅ **Require a pull request before merging** — blocks all direct pushes
     to `master`; the only path in is a reviewed PR
   - ✅ **Require status checks to pass before merging**
     - Search for and add: **`Test`**
     - Search for and add: **`Lint`**
   - ✅ **Require branches to be up to date before merging** — this checkbox
     only appears after at least one required check has been added above;
     prevents stale PRs from merging without re-running checks against the
     latest master
5. Save the rule

Once configured, GitHub blocks the merge button until all required checks pass.

---

## Dealing with Failures

| Failing job / step | Likely cause | Fix |
|--------------------|--------------|-----|
| `black` | Code not formatted | Run `black .` locally and commit |
| `isort` | Imports out of order | Run `isort .` locally and commit |
| `flake8` | Style or docstring violation | Check the error output for file/line; fix manually |
| `Test` | One or more tests failed | Check the Actions log for the failing assertion |
| `bandit` | Security issue in code | Review; fix or suppress with `# nosec` if it is a confirmed false positive |
| `safety` | Vulnerable dependency | Update the package or open a tracking issue |

---

## Running Checks Locally

```bash
# Auto-fix formatting
black .
isort .

# Check without modifying (mirrors CI)
black --check --diff .
isort --check-only --diff .
flake8 .

# Full test suite with coverage
pytest --cov=. --cov-report=term-missing -q

# Security scans
bandit -r . --exclude ./tests,./venv,./.venv --skip B104 -ll
safety check --full-report
```
