# Contributing to VMware Monitor

Thank you for your interest in contributing to VMware Monitor!

## Important: Read-Only Repository

This repository is **read-only by design**. Any PR that introduces destructive operations (power off, delete, create, reconfigure, snapshot manipulation, clone, migrate) will be rejected. For such features, contribute to [VMware-AIops](https://github.com/zw008/VMware-AIops) instead.

## How to Contribute

### Reporting Bugs

[Open an issue](https://github.com/zw008/VMware-Monitor/issues/new?template=bug_report.yml) with:

- A clear description of the problem
- Steps to reproduce
- Expected vs actual behavior
- Your environment (Python version, vSphere version, OS)
- Error messages or logs (with passwords redacted)

### Suggesting Features

[Open a feature request](https://github.com/zw008/VMware-Monitor/issues/new?template=feature_request.yml). Remember: only **read-only** monitoring features are accepted.

### Submitting Code

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Set up the development environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
4. **Make your changes** and write tests
5. **Verify no destructive code**:
   ```bash
   grep -r "power_on\|power_off\|delete_vm\|create_vm\|reconfigure\|clone_vm\|migrate_vm" vmware_monitor/
   # Must return zero results
   ```
6. **Test your changes**: `pytest`
7. **Commit** with a clear message: `git commit -m "feat: add new monitoring feature"`
8. **Push** and open a Pull Request

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — New feature
- `fix:` — Bug fix
- `docs:` — Documentation changes
- `refactor:` — Code refactoring
- `test:` — Adding or updating tests
- `chore:` — Maintenance tasks

## Development Guidelines

### Code Style

- Follow PEP 8 conventions
- Use type annotations on function signatures
- Keep functions focused and small

### Security

- **NEVER** hardcode passwords or credentials
- **NEVER** log or print sensitive information
- **ALWAYS** use `ConnectionManager.from_config()` for connections
- **ALWAYS** store credentials in `~/.vmware-monitor/.env` with `chmod 600`

### Testing

- Test against both vCenter and standalone ESXi when possible
- Mock pyVmomi objects for unit tests
- Redact all credentials in test fixtures

## Getting Help

- Email: zhouwei008@gmail.com
- [Open an issue](https://github.com/zw008/VMware-Monitor/issues)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
