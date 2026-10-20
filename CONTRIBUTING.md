# Contributing

Thanks for your interest in contributing.

## Workflow

1. Fork and create a feature branch from `main`.
2. Make one logical change per pull request.
3. Add or extend tests for any behavior you change.
4. Run the checks below before opening the PR.

## Checks

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e '.[dev]'
ruff check .
pytest -q --cov
```

## Standards

- Every number in docs must come from a command you ran.
- No placeholder functions, stub modules, or filler files.
- Keep the README front page short; depth belongs in `docs/`.
- Commit messages use conventional prefixes: `feat`, `fix`, `test`, `docs`, `ci`, `build`, `chore`.

## Questions

Open an issue, or contact security@rodgersintelligence.com for anything sensitive.
