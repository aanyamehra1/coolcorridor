# Ensures the project root is on sys.path regardless of how pytest is
# invoked (bare `pytest`, `python -m pytest`, or from an IDE), since the
# service modules are imported as top-level packages (e.g. `services.metrics`)
# rather than as a namespaced `coolcorridor.services.metrics` package.
