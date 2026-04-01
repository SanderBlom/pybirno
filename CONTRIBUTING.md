# Contributing to pybirno

Thanks for your interest in contributing! This is a small library, so the process is straightforward.

## Getting started

1. Fork the repository and clone it locally.
2. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```

3. Create a branch for your change:

   ```bash
   git checkout -b my-feature
   ```

## Development

### Running tests

```bash
pytest
```

### Linting and formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for both linting and formatting:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

### Type checking

```bash
mypy src/
```

## Pull requests

- Keep changes focused — one feature or fix per PR.
- Add tests for new functionality.
- Make sure all tests pass and `ruff check` is clean before submitting.
- Use clear commit messages that describe what changed and why.
- **Dependencies**: This project aims to keep dependencies to a minimum. If your change introduces a new dependency, please provide a strong justification for why it is needed and why the standard library or existing dependencies are not sufficient.

## Reporting issues

- Use [GitHub Issues](https://github.com/SanderBlom/pybirno/issues) for bugs and feature requests.
- For security vulnerabilities, see [SECURITY.md](SECURITY.md).
