# Contributing

1. `pip install -e ".[dev]"` then `pytest`.
2. A new check = one function in `src/bunu/rules/`, a test, and a stable issue code.
3. Rules must never modify data, never raise on odd dtypes, and reuse `Context` caches.
4. Scope is deliberately small: diagnose and compare, do not clean.
